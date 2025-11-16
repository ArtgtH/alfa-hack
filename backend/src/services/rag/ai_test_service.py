# import asyncio
# import json
# from asyncio.tasks import gather
# from typing import AsyncGenerator, Sequence
#
# from db.models import Message, MessageType, DocumentChunk, User
# from db.repositories.document_repo import ParsedDocumentRepository
# from services.document_service import get_chunks_for_document
#
#
# class AIService:
#     async def generate_stream_response(
#         self,
#         user_message: str,
#     ) -> AsyncGenerator[str, None]:
#         """
#         Мок-реализация потокового ответа от ИИ
#         Имитирует реальный API с задержками и постепенным выводом
#         """
#         # Анализируем сообщение пользователя для персонализированного ответа
#         response_template = self._generate_response_template(user_message)
#
#         # Разбиваем ответ на chunks для имитации потоковой передачи
#         chunks = self._split_into_chunks(response_template)
#
#         # Имитируем задержки сети и обработки
#         for i, chunk in enumerate(chunks):
#             # Добавляем случайную задержку между 0.1 и 0.3 секунды
#             delay = 0.1 + (i * 0.02)
#             await asyncio.sleep(delay)
#
#             # Иногда добавляем дополнительную задержку для реалистичности
#             if i % 5 == 0:
#                 await asyncio.sleep(0.2)
#
#             yield chunk
#
#     def _generate_response_template(self, user_message: str) -> str:
#         """Генерирует ответ на основе сообщения пользователя"""
#         user_message_lower = user_message.lower()
#
#         if any(word in user_message_lower for word in ["привет", "hello", "hi"]):
#             return "Привет! Рад вас видеть. Чем могу помочь сегодня?"
#
#         elif any(word in user_message_lower for word in ["погод", "weather"]):
#             return "К сожалению, у меня нет доступа к актуальным данным о погоде. Но могу помочь с анализом документов или ответить на другие вопросы!"
#
#         elif any(word in user_message_lower for word in ["документ", "file", "pdf"]):
#             return "Я могу помочь вам проанализировать документы. Загрузите файлы через интерфейс, и я смогу ответить на вопросы по их содержанию."
#
#         elif any(word in user_message_lower for word in ["помощь", "help", "commands"]):
#             return "Я могу:\n- Отвечать на вопросы\n- Анализировать документы\n- Помогать с финансовыми расчетами\n- Объяснять сложные концепции\n\nЧто вас интересует?"
#
#         elif "?" in user_message:
#             return "Это интересный вопрос! Давайте разберем его подробнее. На основе предоставленной информации, я могу сказать, что..."
#
#         else:
#             return f"Спасибо за ваше сообщение: '{user_message}'. Я проанализировал запрос и могу предложить следующее: это типичная ситуация, которая требует внимательного подхода. Рекомендую рассмотреть несколько вариантов решения."
#
#     def _split_into_chunks(self, text: str) -> list[str]:
#         """Разбивает текст на chunks для потоковой передачи"""
#         words = text.split()
#         chunks = []
#         current_chunk = ""
#
#         for word in words:
#             # Добавляем слово к текущему chunk
#             if current_chunk:
#                 current_chunk += " " + word
#             else:
#                 current_chunk = word
#
#             # Случайно решаем, закончить ли chunk (имитация реального API)
#             if len(current_chunk) > 3 and (len(chunks) < 2 or len(current_chunk) > 8):
#                 chunks.append(current_chunk)
#                 current_chunk = ""
#
#         # Добавляем последний chunk если остался
#         if current_chunk:
#             chunks.append(current_chunk)
#
#         return chunks
#
#
# async def generate_ai_response(
#     user_message: str,
#     user: User,
#     chat_id: int,
#     message_repo,
#     documents,
#     db,
# ) -> AsyncGenerator[str, None]:
#     ai_service = AIService()
#     full_response = ""
#
#     documents = documents or [
#         document.document_id
#         for document in await ParsedDocumentRepository(db).get_all_for_user(user)
#     ]
#
#     chunks_lists: list[Sequence[DocumentChunk]] = await gather(
#         *(get_chunks_for_document(db, document_id) for document_id in documents)
#     )
#
#     try:
#         async for chunk in ai_service.generate_stream_response(
#             user_message=user_message,
#         ):
#             full_response += chunk
#             yield f"data: {json.dumps({'content': chunk})}\n\n"
#
#         ai_message = Message(
#             content=full_response,
#             message_type=MessageType.MODEL,
#             chat_id=chat_id,
#         )
#         await message_repo.create(ai_message)
#
#         yield f"data: {json.dumps({'done': True})}\n\n"
#
#     except Exception as e:
#         yield f"data: {json.dumps({'error': str(e)})}\n\n"
