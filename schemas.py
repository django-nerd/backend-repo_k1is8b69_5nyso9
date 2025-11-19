"""
Database Schemas for DreamNest (FastAPI + MongoDB)

Each Pydantic model corresponds to a MongoDB collection. The collection
name is the lowercase of the class name (e.g., Community -> "community").
These schemas are used for validation in the API layer.
"""
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any

# Core domain schemas
class Community(BaseModel):
    name: str
    city: str
    starting_price: Optional[float] = Field(None, ge=0)
    image_url: Optional[str] = None
    amenities_images: List[str] = []

class Tower(BaseModel):
    name: str
    community_id: str = Field(..., description="Related community id (string)")
    images: List[str] = []
    pdfs: List[str] = []

class Flat(BaseModel):
    number: str
    tower_id: str
    bhk_type: str
    status: str = Field("available", pattern=r"^(available|booked|sold)$")
    images: List[str] = []

class FloorPlan(BaseModel):
    bhk_type: str
    image_url: Optional[str] = None
    pdf_url: Optional[str] = None
    carpet_area: Optional[float] = Field(None, ge=0)
    uds_area: Optional[float] = Field(None, ge=0)

class FollowUp(BaseModel):
    lead_id: str
    notes: str
    next_date: Optional[str] = Field(None, description="ISO date string")
    type: str = Field("call", pattern=r"^(call|visit|whatsapp)$")
    agent_id: Optional[str] = None

class Lead(BaseModel):
    name: str
    phone: str
    email: Optional[str] = None
    assigned_agent_id: Optional[str] = None
    assigned_manager_id: Optional[str] = None
    requirement_type: Optional[str] = None
    source: Optional[str] = None
    status: str = Field("New")
    follow_up_ids: List[str] = []

class QuotationInputs(BaseModel):
    area: float = Field(..., ge=0)
    rate_per_sqft: float = Field(..., ge=0)
    material_cost: float = Field(0, ge=0)
    gst_percent: float = Field(18.0, ge=0)
    markup_percent: float = Field(10.0, ge=0)

class Quotation(BaseModel):
    lead_id: str
    project_id: Optional[str] = None  # community or tower id
    pricing_inputs: QuotationInputs
    generated_price: float = Field(..., ge=0)
    pdf_url: Optional[str] = None
    created_by: Optional[str] = None  # agent/manager id

class User(BaseModel):
    role: str = Field(..., pattern=r"^(customer|agent|manager|admin)$")
    name: str
    email: Optional[str] = None
    phone: Optional[str] = None
    avatar_url: Optional[str] = None

# Utility: minimal schema manifest (used optionally by any viewer)
class SchemaManifest(BaseModel):
    collections: List[str]

SCHEMA_MANIFEST = SchemaManifest(
    collections=[
        "community",
        "tower",
        "flat",
        "floorplan",
        "followup",
        "lead",
        "quotation",
        "user",
    ]
)
