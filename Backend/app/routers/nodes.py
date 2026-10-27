from fastapi import APIRouter, Depends

from app.engine.registry import NodeRegistry, get_registry
from app.schemas.node import NodeCatalogueEntry

router = APIRouter(prefix="/api/nodes", tags=["nodes"])


@router.get("", response_model=list[NodeCatalogueEntry])
async def list_nodes(registry: NodeRegistry = Depends(get_registry)) -> list[NodeCatalogueEntry]:
    return [
        NodeCatalogueEntry(
            id=plugin.id,
            display_name=plugin.display_name,
            category=plugin.category,
            config_schema=plugin.get_config_schema(),
            formula_exportable=plugin.formula_exportable,
            input_ports=plugin.input_ports,
            output_ports=plugin.output_ports,
        )
        for plugin in registry.all()
    ]
