from models.data_type import DataType
from models.column import Column
from models.data_schema import DataSchema
from models.data_frame import DataFrame
from nodes.base import NodePlugin, FieldSchema, NodeRegistry

def test_dataframe():
    schema = DataSchema(columns=[
        Column(name="name", type=DataType.STRING),
        Column(name="age", type=DataType.NUMBER)
    ])
    rows = [{"name": "Samir", "age": 22}, {"name": "Ifham", "age": 22}]
    df = DataFrame(schema=schema, rows=rows, total_row_count=2)
    
    preview = df.preview(1)
    assert len(preview.rows) == 1
    print("DataFrame test passed")

def test_registry():
    class DummyNode(NodePlugin):
        def get_id(self): return "dummy"
        def get_display_name(self): return "Dummy"
        def get_category(self): return "TRANSFORM"
        def get_config_schema(self): return []
        def infer_output_schema(self, input_schema, config): return input_schema
    
    NodeRegistry.register(DummyNode())
    assert NodeRegistry.get("dummy") is not None
    print("Registry test passed")

if __name__ == "__main__":
    test_dataframe()
    test_registry()
    print("All tests passed")