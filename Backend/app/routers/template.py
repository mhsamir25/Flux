"""/api/templates/* — auth required throughout """
import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import current_active_user
from app.auth.models import User
from app.db import get_session
from app.models.pipeline_template import PipelineTemplate
from app.schemas.template import TemplateCreate, TemplateOut, TemplateUpdate

router = APIRouter(prefix="/api/templates", tags=["templates"])


@router.get("", response_model=list[TemplateOut])
async def list_templates(
    user: User = Depends(current_active_user), session: AsyncSession = Depends(get_session)
) -> list[PipelineTemplate]:
    result = await session.execute(
        select(PipelineTemplate).where(PipelineTemplate.owner_id == user.id)
    )
    return list(result.scalars().all())


@router.post("", response_model=TemplateOut, status_code=201)
async def create_template(
    payload: TemplateCreate,
    user: User = Depends(current_active_user),
    session: AsyncSession = Depends(get_session),
) -> PipelineTemplate:
    template = PipelineTemplate(
        id=uuid.uuid4(), owner_id=user.id, name=payload.name,
        description=payload.description, pipeline_json=payload.pipeline_json,
    )
    session.add(template)
    await session.commit()
    await session.refresh(template)
    return template


@router.get("/{template_id}", response_model=TemplateOut)
async def get_template(
    template_id: uuid.UUID,
    user: User = Depends(current_active_user),
    session: AsyncSession = Depends(get_session),
) -> PipelineTemplate:
    return await _get_owned_template(session, template_id, user.id)


@router.put("/{template_id}", response_model=TemplateOut)
async def update_template(
    template_id: uuid.UUID,
    payload: TemplateUpdate,
    user: User = Depends(current_active_user),
    session: AsyncSession = Depends(get_session),
) -> PipelineTemplate:
    template = await _get_owned_template(session, template_id, user.id)
    if payload.name is not None:
        template.name = payload.name
    if payload.description is not None:
        template.description = payload.description
    if payload.pipeline_json is not None:
        template.pipeline_json = payload.pipeline_json
    await session.commit()
    await session.refresh(template)
    return template


@router.delete("/{template_id}", status_code=204)
async def delete_template(
    template_id: uuid.UUID,
    user: User = Depends(current_active_user),
    session: AsyncSession = Depends(get_session),
) -> None:
    template = await _get_owned_template(session, template_id, user.id)
    await session.delete(template)
    await session.commit()


async def _get_owned_template(
    session: AsyncSession, template_id: uuid.UUID, owner_id: uuid.UUID
) -> PipelineTemplate:
    result = await session.execute(
        select(PipelineTemplate).where(
            PipelineTemplate.id == template_id, PipelineTemplate.owner_id == owner_id
        )
    )
    template = result.scalar_one_or_none()
    if template is None:
        raise HTTPException(status_code=404, detail="Template not found.")
    return template
