from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Sequence
import math

import structlog

from sqlalchemy.ext.asyncio import AsyncSession

from db.models import ParsedDocument, User
from db.repositories.document_repo import ParsedDocumentRepository
from db.repositories.message_repo import MessageRepository
from services.document_processing.vector_manager import (
    DocumentVectorManager,
    VectorSearchResult,
)
from services.rag.openrouter_chat import OpenRouterChatClient


logger = structlog.get_logger(__name__)


@dataclass
class AgentResult:
    answer: str
    used_chunks: list[VectorSearchResult]
    scenario: int
    debug: dict[str, Any]


@dataclass
class ScenarioDecision:
    scenario: int
    confidence: float
    reason: str
    follow_up: bool
    clarifications: list[str]
    use_query_expansion: bool | None


class VectorSearchError(Exception):
    """Raised when vector search cannot be completed."""


class RagAgent:
    def __init__(
        self,
        *,
        chat_client: OpenRouterChatClient | None = None,
        vector_manager: DocumentVectorManager | None = None,
        messages_limit: int = 20,
        max_context_chars: int = 50_000,
        default_top_k: int = 8,
        default_score_threshold: float | None = 0.7,
        use_query_expansion: bool = True,
        rrf_k: int = 60,
    ) -> None:
        self._chat = chat_client or OpenRouterChatClient.from_settings()
        self._vectors = vector_manager or DocumentVectorManager()
        self._messages_limit = messages_limit
        self._max_context_chars = max_context_chars
        self._top_k = default_top_k
        self._score_threshold = default_score_threshold
        self._use_query_expansion = use_query_expansion
        self._rrf_k = rrf_k

    async def run(
        self,
        *,
        db: AsyncSession,
        user: User,
        query: str,
        chat_id: int | None = None,
        selected_document_ids: Sequence[int] | None = None,
        answer_instructions: str | None = None,
    ) -> AgentResult:
        history = await self._load_chat_history(db, chat_id) if chat_id else []
        decision = await self._choose_scenario(query=query, history=history, selected_ids=selected_document_ids)
        scenario = decision.scenario

        used_chunks: list[VectorSearchResult] = []
        answer = ""
        run_use_query_expansion = (
            decision.use_query_expansion if decision.use_query_expansion is not None else self._use_query_expansion
        )
        debug: dict[str, Any] = {
            "history_len": len(history),
            "scenario": scenario,
            "scenario_decision": {
                "confidence": decision.confidence,
                "reason": decision.reason,
                "follow_up": decision.follow_up,
                "clarifications": decision.clarifications,
                "use_query_expansion": run_use_query_expansion,
            },
        }

        instructions = self._resolve_instructions(answer_instructions)

        if scenario == 2 and selected_document_ids:
            docs, total_len = await self._load_documents(db, selected_document_ids)
            if total_len <= self._max_context_chars:
                answer = await self._answer_with_full_context(
                    query=query,
                    history=history,
                    documents=docs,
                    instructions=instructions,
                )
            else:
                try:
                    if run_use_query_expansion:
                        used_chunks, qx_debug = await self._search_with_expansion(
                            db=db, user=user, query=query, document_ids=selected_document_ids
                        )
                        debug["query_expansion"] = qx_debug
                    else:
                        used_chunks = await self._search_chunks(
                            db=db, user=user, query=query, document_ids=selected_document_ids
                        )
                    answer = await self._answer_with_chunks(
                        query=query,
                        history=history,
                        chunks=used_chunks,
                        instructions=instructions,
                    )
                except VectorSearchError as exc:
                    logger.warning("vector-search-unavailable", reason=str(exc))
                    debug["vector_search_error"] = str(exc)
                    answer = self._vector_search_unavailable_message()
        elif scenario == 1:
            try:
                if run_use_query_expansion:
                    used_chunks, qx_debug = await self._search_with_expansion(
                        db=db, user=user, query=query, document_ids=None
                    )
                    debug["query_expansion"] = qx_debug
                else:
                    used_chunks = await self._search_chunks(db=db, user=user, query=query, document_ids=None)
                answer = await self._answer_with_chunks(
                    query=query,
                    history=history,
                    chunks=used_chunks,
                    instructions=instructions,
                )
            except VectorSearchError as exc:
                logger.warning("vector-search-unavailable", reason=str(exc))
                debug["vector_search_error"] = str(exc)
                answer = self._vector_search_unavailable_message()
        elif scenario == 4:
            answer = await self._answer_general(query=query, history=history, instructions=instructions)
        else:  # scenario 3 или уточнение
            answer = await self._ask_clarification(query=query, history=history, clarifications=decision.clarifications)

        return AgentResult(answer=answer, used_chunks=used_chunks, scenario=scenario, debug=debug)

    async def _load_chat_history(self, db: AsyncSession, chat_id: int) -> list[dict[str, str]]:
        msgs = await MessageRepository(db).get_last_for_chat(chat_id=chat_id, limit=self._messages_limit)
        history: list[dict[str, str]] = []
        for m in msgs:
            role = "assistant" if m.message_type.name == "MODEL" else "user"
            history.append({"role": role, "content": m.content})
        return history

    async def _choose_scenario(
        self,
        *,
        query: str,
        history: list[dict[str, str]],
        selected_ids: Sequence[int] | None,
    ) -> ScenarioDecision:
        from pathlib import Path

        base = Path(__file__).with_suffix("").parent / "prompt_storage"
        system_prompt = (base / "system_ru.txt").read_text(encoding="utf-8")
        orchestrator_prompt = (base / "orchestrator_ru.txt").read_text(encoding="utf-8")

        rule_guess = self._rule_guess_scenario(query=query, history=history, selected_ids=selected_ids)
        sys_msg = {"role": "system", "content": system_prompt}
        orch_msg = {"role": "system", "content": orchestrator_prompt}
        user_msg = {
            "role": "user",
            "content": json.dumps(
                {
                    "query": query,
                    "selected_document_ids": list(selected_ids or []),
                    "has_history": bool(history),
                    "rule_guess": rule_guess,
                    "history_messages": len(history),
                },
                ensure_ascii=False,
            ),
        }

        messages = [sys_msg, orch_msg, *history[-5:], user_msg]
        resp = await self._chat.chat(
            messages=messages, temperature=0.0, top_p=1.0, max_tokens=400, response_format={"type": "json_object"}
        )
        try:
            content = resp["choices"][0]["message"]["content"]
            parsed = json.loads(content)
            llm_scenario = int(parsed.get("scenario", 3))
            confidence = float(parsed.get("confidence", 0.5))
            scenario = llm_scenario if confidence >= 0.6 else rule_guess
            clarifications = [str(item) for item in parsed.get("clarifications", [])][:3]
            use_qe = parsed.get("use_query_expansion")
            if isinstance(use_qe, str):
                use_qe = use_qe.lower() in {"true", "1", "yes"}
            decision = ScenarioDecision(
                scenario=scenario,
                confidence=confidence,
                reason=str(parsed.get("reason", "")),
                follow_up=bool(parsed.get("follow_up", False)),
                clarifications=clarifications,
                use_query_expansion=use_qe if use_qe is not None else None,
            )
        except Exception:
            decision = ScenarioDecision(
                scenario=rule_guess,
                confidence=0.0,
                reason="rule fallback",
                follow_up=False,
                clarifications=[],
                use_query_expansion=None,
            )
        return decision

    def _rule_guess_scenario(
        self, *, query: str, history: list[dict[str, str]], selected_ids: Sequence[int] | None
    ) -> int:
        if selected_ids and len(selected_ids) > 0:
            return 2
        q = (query or "").lower()
        search_keywords = (
            "найти",
            "найди",
            "ищи",
            "поиск",
            "где",
            "какой договор",
            "какой документ",
            "покажи",
            "подбери",
        )
        if any(k in q for k in search_keywords):
            return 1
        if not history:
            return 3
        return 4

    async def _load_documents(
        self, db: AsyncSession, document_ids: Sequence[int]
    ) -> tuple[list[ParsedDocument], int]:
        docs = await ParsedDocumentRepository(db).get_many_by_ids(list(document_ids))
        total_len = sum(len(d.content) for d in docs if d.content)
        return list(docs), int(total_len)

    async def _search_chunks(
        self,
        *,
        db: AsyncSession,
        user: User,
        query: str,
        document_ids: Sequence[int] | None,
    ) -> list[VectorSearchResult]:
        from services.document_service import search_document_chunks

        try:
            results = await search_document_chunks(
                db=db,
                user=user,
                query=query,
                limit=self._top_k,
                score_threshold=self._score_threshold,
                document_ids=document_ids,
            )
        except Exception as exc:  # pragma: no cover - network/infra issues
            logger.error("vector-search-failed", reason=str(exc))
            raise VectorSearchError("Vector search is currently unavailable") from exc
        return list(results)

    async def _search_with_expansion(
        self,
        *,
        db: AsyncSession,
        user: User,
        query: str,
        document_ids: Sequence[int] | None,
    ) -> tuple[list[VectorSearchResult], dict[str, Any]]:
        from services.document_service import search_document_chunks

        refinements, subqueries, notes = await self._expand_query(query=query)
        expansions: list[str] = [query] + [*refinements, *subqueries]
        expansions = [e for e in expansions if e and e.strip()]
        if not expansions:
            plain = await self._search_chunks(
                db=db, user=user, query=query, document_ids=document_ids
            )
            return list(plain), {"expansions": [], "strategy": "plain"}

        per_query = max(2, math.ceil(self._top_k / len(expansions)))
        results_by_query: list[list[VectorSearchResult]] = []
        try:
            for q in expansions:
                r = await search_document_chunks(
                    db=db,
                    user=user,
                    query=q,
                    limit=per_query,
                    score_threshold=self._score_threshold,
                    document_ids=document_ids,
                )
                results_by_query.append(list(r))
        except Exception as exc:  # pragma: no cover - network/infra issues
            logger.error("vector-search-expansion-failed", reason=str(exc))
            raise VectorSearchError("Expanded vector search is currently unavailable") from exc

        fused = self._rrf_merge(results_by_query=results_by_query, k=self._rrf_k, limit=self._top_k)
        debug = {"expansions": expansions, "notes": notes, "per_query": per_query, "merged": len(fused)}
        return fused, debug

    async def _expand_query(self, *, query: str) -> tuple[list[str], list[str], str]:
        from pathlib import Path

        base = Path(__file__).with_suffix("").parent / "prompt_storage"
        system_prompt = (base / "system_ru.txt").read_text(encoding="utf-8")
        fusion_prompt = (base / "fusion_ru.txt").read_text(encoding="utf-8")

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "system", "content": fusion_prompt},
            {"role": "user", "content": json.dumps({"query": query}, ensure_ascii=False)},
        ]
        resp = await self._chat.chat(
            messages=messages,
            temperature=0.2,
            top_p=0.95,
            max_tokens=500,
            response_format={"type": "json_object"},
        )
        try:
            content = resp["choices"][0]["message"]["content"]
            parsed = json.loads(content)
            refinements = list(parsed.get("refinements", []))
            subqueries = list(parsed.get("subqueries", []))
            notes = str(parsed.get("notes", "")) if parsed.get("notes") is not None else ""
            return refinements, subqueries, notes
        except Exception:
            return [], [], ""

    def _answer_format_instructions(self) -> str:
        return (
            "Сформируй ответ в Markdown с разделами:"
            "\n## Краткий вывод"
            "\n- 1–2 предложения с главным выводом."
            "\n## Подробный анализ"
            "\n- Подзаголовки по аспектам вопроса;"
            "\n- для каждого факта указывай ссылки на документы в формате [Название](URL);"
            "\n- избегай ссылок на чанки, используй только ссылки на целые документы."
            "\n## Источники"
            "\n- Маркированный список: - [Название документа](URL) — краткое содержание выдержки;"
            "\n- если URL отсутствует, напиши ‘ссылка недоступна’."
            "\nЕсли источников нет, явно сообщи об их отсутствии."
        )

    def _rrf_merge(
        self, *, results_by_query: list[list[VectorSearchResult]], k: int, limit: int
    ) -> list[VectorSearchResult]:
        # Reciprocal Rank Fusion across multiple query result lists
        rank_maps: list[dict[int, int]] = []
        for lst in results_by_query:
            rank_map: dict[int, int] = {}
            for idx, res in enumerate(lst):
                rank_map[res.chunk.chunk_id] = idx + 1  # ranks start at 1
            rank_maps.append(rank_map)

        fused_scores: dict[int, float] = {}
        best_result_for_chunk: dict[int, VectorSearchResult] = {}
        for lst in results_by_query:
            for idx, res in enumerate(lst):
                cid = res.chunk.chunk_id
                # use min rank across lists where chunk appears; sum 1/(k+rank) per list
                score_sum = fused_scores.get(cid, 0.0)
                rank = idx + 1
                score_sum += 1.0 / (k + rank)
                fused_scores[cid] = score_sum
                # keep the best scoring instance to carry payload and text
                if cid not in best_result_for_chunk or res.score > best_result_for_chunk[cid].score:
                    best_result_for_chunk[cid] = res

        fused = [
            (cid, score, best_result_for_chunk[cid]) for cid, score in fused_scores.items()
        ]
        fused.sort(key=lambda x: x[1], reverse=True)
        top_results: list[VectorSearchResult] = []
        for _, _, res in fused[:limit]:
            top_results.append(res)
        return top_results

    def _resolve_instructions(self, custom_value: str | None) -> str:
        if custom_value:
            stripped = custom_value.strip()
            if stripped:
                return stripped
        return self._answer_format_instructions()

    async def _answer_with_full_context(
        self,
        *,
        query: str,
        history: list[dict[str, str]],
        documents: Sequence[ParsedDocument],
        instructions: str,
    ) -> str:
        from pathlib import Path

        base = Path(__file__).with_suffix("").parent / "prompt_storage"
        system_prompt = (base / "system_ru.txt").read_text(encoding="utf-8")

        context_parts: list[str] = []
        for idx, d in enumerate(documents, start=1):
            name = d.filename or f"Документ {d.document_id}"
            url = d.minio_url or "н/д"
            created = d.created_at.isoformat() if getattr(d, "created_at", None) else "н/д"
            content = d.content or ""
            link_display = f"[Открыть документ]({url})" if url != "н/д" else "ссылка недоступна"
            snippet = (
                f"### Документ {idx}: {name} (ID {d.document_id})\n"
                f"- Ссылка: {link_display}\n"
                f"- Дата загрузки: {created}\n"
                f"- Объём: {len(content)} символов\n\n"
                f"```markdown\n{content}\n```"
            )
            context_parts.append(snippet)
        context = "\n\n---\n\n".join(context_parts)

        user_content = (
            f"Вопрос клиента: {query}\n\n"
            f"Инструкции по ответу:\n{instructions}\n\n"
            "Ниже приведён контекст выбранных документов в формате Markdown. Используй его для ссылок и цитирования."
            f"\n\n{context}"
        )

        messages = [
            {"role": "system", "content": system_prompt},
            *history[-self._messages_limit :],
            {"role": "user", "content": user_content},
        ]
        resp = await self._chat.chat(messages=messages, temperature=0.2, top_p=0.9, max_tokens=1500)
        return resp["choices"][0]["message"]["content"]

    async def _answer_with_chunks(
        self,
        *,
        query: str,
        history: list[dict[str, str]],
        chunks: Sequence[VectorSearchResult],
        instructions: str,
    ) -> str:
        from pathlib import Path

        base = Path(__file__).with_suffix("").parent / "prompt_storage"
        system_prompt = (base / "system_ru.txt").read_text(encoding="utf-8")

        snippets: list[str] = []
        for idx, r in enumerate(chunks, start=1):
            payload = r.payload or {}
            title = payload.get("filename") or f"Документ {payload.get('document_id', 'н/д')}"
            doc_id = payload.get("document_id")
            serial = r.chunk.chunk_serial
            url = (
                payload.get("minio_url")
                or (payload.get("document_metadata") or {}).get("minio_url")
                or "н/д"
            )
            snippet_text = r.chunk.chunk_content.strip()
            link_display = f"[{title}]({url})" if url != "н/д" else f"{title} (ссылка недоступна)"
            snippet_block = (
                f"### Источник {idx}: {title} (Документ {doc_id}, чанк {serial})"
                f"\n- Ссылка: {link_display}"
                f"\n- Оценка сходства: {r.score:.3f}"
                f"\n- Чанк: {serial}"
                f"\n\n```markdown\n{snippet_text}\n```"
            )
            snippets.append(snippet_block)
        context = "\n\n---\n\n".join(snippets)

        user_content = (
            f"Вопрос клиента: {query}\n\n"
            f"Инструкции по ответу:\n{instructions}\n\n"
            "Ниже приведены релевантные фрагменты документов с метаданными. Используй их и укажи ссылки на источники в формате [[Источник: …]]."
            f"\n\n{context}"
        )

        messages = [
            {"role": "system", "content": system_prompt},
            *history[-self._messages_limit :],
            {"role": "user", "content": user_content},
        ]
        resp = await self._chat.chat(messages=messages, temperature=0.2, top_p=0.9, max_tokens=1200)
        return resp["choices"][0]["message"]["content"]

    def _vector_search_unavailable_message(self) -> str:
        return (
            "Не удалось подключиться к базе векторного поиска документов. "
            "Пожалуйста, повторите запрос чуть позже или сообщите администратору, если проблема сохраняется."
        )

    async def _answer_general(
        self,
        *,
        query: str,
        history: list[dict[str, str]],
        instructions: str,
    ) -> str:
        from pathlib import Path

        base = Path(__file__).with_suffix("").parent / "prompt_storage"
        system_prompt = (base / "system_ru.txt").read_text(encoding="utf-8")

        user_content = (
            f"Вопрос клиента: {query}\n\n"
            f"Инструкции по ответу:\n{instructions}\n\n"
            "Используй последние сообщения чата (выше) для контекста. Если источников нет, всё равно сохрани требуемую структуру и поясни отсутствие ссылок."
        )

        messages = [
            {"role": "system", "content": system_prompt},
            *history[-self._messages_limit :],
            {"role": "user", "content": user_content},
        ]
        resp = await self._chat.chat(messages=messages, temperature=0.3, top_p=0.9, max_tokens=900)
        return resp["choices"][0]["message"]["content"]

    async def _ask_clarification(
        self,
        *,
        query: str,
        history: list[dict[str, str]],
        clarifications: Sequence[str] | None = None,
    ) -> str:
        from pathlib import Path

        base = Path(__file__).with_suffix("").parent / "prompt_storage"
        system_prompt = (base / "system_ru.txt").read_text(encoding="utf-8")

        extra = ""
        if clarifications:
            bullets = "\n".join(f"- {c}" for c in clarifications)
            extra = "Дополнительно попроси уточнить следующие моменты:\n" + bullets + "\n\n"
        prompt_text = (
            "Недостаточно информации, чтобы выполнить поиск по документам. "
            "Сформулируй 1-3 уточняющих вопроса на русском, чтобы определить релевантные документы или условия. "
            "Зафиксируй вопросы в виде маркированного списка."
        )
        user_content = f"{query}\n\n{extra}{prompt_text}"

        messages = [
            {"role": "system", "content": system_prompt},
            *history[-self._messages_limit :],
            {"role": "user", "content": user_content},
        ]
        resp = await self._chat.chat(messages=messages, temperature=0.2, top_p=0.9, max_tokens=400)
        return resp["choices"][0]["message"]["content"]
