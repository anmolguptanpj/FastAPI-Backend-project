
import shutil

from fastapi import FastAPI,HTTPException,File,UploadFile,Form,Depends

from app.db import Post,create_db_and_tables,get_async_session
from sqlalchemy.ext.asyncio import AsyncSession
from contextlib import asynccontextmanager
from sqlalchemy import select
from app.images import imagekit
import shutil
import os 
import uuid
import tempfile
from app.users import auth_backend, current_active_user, fastapi_users
from app.schemas import UserUpdate,UserCreate,UserRead
from app.db import User




@asynccontextmanager
async def lifespan(app:FastAPI):
  await create_db_and_tables()
  yield

app = FastAPI(lifespan=lifespan)

app.include_router(fastapi_users.get_auth_router(auth_backend),prefix='/auth/jwt',tags=["auth"])
app.include_router(fastapi_users.get_register_router(UserRead,UserCreate),prefix="/auth",tags=["auth"])
app.include_router(fastapi_users.get_reset_password_router(),prefix="/auth",tags=["auth"])
app.include_router(fastapi_users.get_verify_router(UserRead),prefix="/auth",tags=["auth"])
app.include_router(fastapi_users.get_users_router(UserRead,UserUpdate),prefix="/users",tags=["users"])


@app.post("/upload")
async def upload_file(
    file: UploadFile = File(...),
    caption: str = Form(""),
    user: User = Depends(current_active_user),
    session: AsyncSession = Depends(get_async_session)
):
    temp_file_path = None

    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=os.path.splitext(file.filename)[1]) as temp_file:
            temp_file_path = temp_file.name
            shutil.copyfileobj(file.file, temp_file)
        await file.close()

        with open(temp_file_path, "rb") as f:
          upload_result = imagekit.files.upload(
              file=f,
              file_name=file.filename,
              tags=["backend-upload"]
          )
          print(upload_result)

        if upload_result:
            post = Post(
                user_id=user.id,
                caption=caption,
                url=upload_result.url,
                file_type="video" if file.content_type.startswith("video/") else "image",
                file_name=upload_result.name
            )
            session.add(post)
            await session.commit()
            await session.refresh(post)
            return post

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    finally:
        if temp_file_path and os.path.exists(temp_file_path):
          try:
            os.unlink(temp_file_path)
          except PermissionError:
            pass

@app.get("/feed")
async def get_feed(
  session:AsyncSession = Depends(get_async_session),
   user: User = Depends(current_active_user)
):
  result = await session.execute(select(Post).order_by(Post.created_at.desc()))
  posts = [row[0] for row in result.all()]

  result = await session.execute(select(User))
  users=[row[0] for row in result.all()]
  user_dict = {u.id: u.email for u in users}

  posts_data = []
  for post in posts:
    posts_data.append({
      "id":str(post.id),
      "user_id":str(post.user_id),
      "caption":post.caption,
      "url":post.url,
      "file_type":post.file_type,
      "file_name":post.file_name,
      "created_at":post.created_at.isoformat(),
      "is_owner":post.user_id== user.id,
      "email":user_dict.get(post.user_id,"unknown")
    })

  return {"posts": posts_data}

@app.delete("/posts/{post_id}")
async def delete_post(post_id:str, user: User = Depends(current_active_user), session:AsyncSession = Depends(get_async_session)):
  try:
    post_uuid = uuid.UUID(post_id)

    result = await session.execute(select(Post).where(Post.id == post_uuid))
    post = result.scalars().first()

    if not post:
      raise HTTPException(status_code=404,detail = "Post not Found")

    if post.user_id != user.id:
      raise HTTPException(status_code=403,detail="You dont have permission to delete this post")
    await session.delete(post)
    await session.commit()
    

    return{"success":True,"message":"Post deleted successfully"}
  except HTTPException:
    raise
  except ValueError:
    raise HTTPException(
      status_code=400,
      detail="Invalid UUID"
    )
  except Exception as e:
      raise HTTPException(status_code=500, detail=str(e))

# @app.get("/hello-world")
# def hello_world():
#     return{"message:": "Hello world"}

# text_posts = {
#   1: {
#     "title": "new post",
#     "content": "cool test post"
#   },
#   2: {
#     "title": "learning fastapi",
#     "content": "building APIs with FastAPI is actually fun"
#   },
#   3: {
#     "title": "late night coding",
#     "content": "debugging at 2am hits differently"
#   },
#   4: {
#     "title": "portfolio upgrade",
#     "content": "working on a cleaner and more standout portfolio design"
#   },
#   5: {
#     "title": "sql practice",
#     "content": "today i practiced joins and aggregate functions"
#   },
#   6: {
#     "title": "machine learning journey",
#     "content": "starting with simple regression models before deep learning"
#   },
#   7: {
#     "title": "cloud deployment",
#     "content": "finally deployed my backend project successfully"
#   },
#   8: {
#     "title": "resume improvements",
#     "content": "small details in resumes can create a huge difference"
#   },
#   9: {
#     "title": "data analysis thoughts",
#     "content": "good visualizations make data easier to understand"
#   },
#   10: {
#     "title": "typescript switch",
#     "content": "moving from javascript to typescript feels more structured"
#   },
#   11: {
#     "title": "consistency matters",
#     "content": "daily progress matters more than motivation"
#   }
# }

# @app.get("/posts")
# def get_all_posts(limit: int = None ):
#     if limit:
#         return list(text_posts.values())[:limit]
#     return text_posts


# @app.get("/posts/{id}")
# def get_post(id:int)-> PostResponse:

#     if id not in text_posts:
#         raise HTTPException(status_code=404,detail="Post not found")
#     return text_posts.get(id)


# @app.post("/posts")
# def create_post(post : PostCreate)-> PostResponse: 
#   new_post = {"title":post.title,"content":post.content}
#   text_posts[max(text_posts.keys())+1 ] = new_post
#   return new_post