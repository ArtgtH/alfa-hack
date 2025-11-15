from fastapi import APIRouter, HTTPException
from starlette import status
from starlette.responses import StreamingResponse

from db.models import Message, MessageType
from db.repositories.chat_repo import ChatRepository
from db.repositories.message_repo import MessageRepository
from db.repositories.prompt_repo import PromptRepository
from internal.dependencies import CtxUser, Db
from internal.schemas.chat import (
    ChatResponse,
    ExpandedChatResponse,
    BaseMessage,
    PromptID,
)
from services.rag.ai_test_service import generate_ai_response

router = APIRouter(prefix="/chat", tags=["chat"])


@router.get("", response_model=list[ChatResponse])
async def get_all_chats(db: Db, user: CtxUser) -> list[ChatResponse]:
    chats = await ChatRepository(db).get_all_for_user(user)
    return [ChatResponse.model_validate(chat) for chat in chats]


@router.get("/{chat_id}", response_model=ExpandedChatResponse)
async def get_chat(db: Db, user: CtxUser, chat_id: int) -> ExpandedChatResponse:
    if (chat := await ChatRepository(db).get_one_by_id(chat_id)) and chat.user == user:
        return ExpandedChatResponse.from_chat(chat)
    raise HTTPException(status_code=404, detail="Chat not found")


@router.post(
    "", response_model=ExpandedChatResponse, status_code=status.HTTP_201_CREATED
)
async def create_chat(
    db: Db, user: CtxUser, prompt_request: PromptID
) -> ExpandedChatResponse:
    if not (
        prompt := await PromptRepository(db).get_one_by_id(prompt_request.prompt_id)
    ):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Prompt not found"
        )

    try:
        chat = await ChatRepository(db).create_new_chat(prompt, user)
        return ExpandedChatResponse.from_chat(chat)

    except Exception as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.delete("/{chat_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_chat(db: Db, user: CtxUser, chat_id: int) -> None:
    chat_repo = ChatRepository(db)

    if (
        not (chat := await chat_repo.get_one_by_id(chat_id))
        or chat.user_id != user.user_id
    ):
        raise HTTPException(status_code=404, detail="Chat not found")

    chat.is_active = False
    await chat_repo.save(chat)


@router.post("/{chat_id}/message")
async def create_message(
    db: Db, user: CtxUser, chat_id: int, message_data: BaseMessage
) -> StreamingResponse:
    chat_repo = ChatRepository(db)

    if (
        not (chat := await chat_repo.get_one_by_id(chat_id))
        or chat.user_id != user.user_id
    ):
        raise HTTPException(status_code=404, detail="Chat not found")

    await chat_repo.set_active(chat_id=chat_id, user=user)

    message_repo = MessageRepository(db)
    user_message = Message(
        content=message_data.content,
        message_type=MessageType.USER,
        chat_id=chat_id,
        documents_ids=message_data.documents_ids,
    )
    await message_repo.create(user_message)

    return StreamingResponse(
        generate_ai_response(
            chat_id=chat_id,
            message_repo=message_repo,
            user_message=user_message.content,
            documents=user_message.documents_ids,
            db=db,
            user=user,
        ),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "Access-Control-Allow-Origin": "*",
            "X-Accel-Buffering": "no",
        },
    )
