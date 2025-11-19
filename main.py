import os
from typing import Any, Dict, List, Optional
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from bson import ObjectId

from database import db, create_document, get_documents
from schemas import (
    Community, Tower, Flat, FloorPlan,
    Lead, FollowUp, QuotationInputs, Quotation,
    SCHEMA_MANIFEST
)

app = FastAPI(title="DreamNest API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------- Utilities ----------------------
class PyObjectId(ObjectId):
    @classmethod
    def __get_validators__(cls):
        yield cls.validate

    @classmethod
    def validate(cls, v):
        if isinstance(v, ObjectId):
            return v
        if not ObjectId.is_valid(v):
            raise ValueError("Invalid ObjectId")
        return ObjectId(v)

def to_serializable(doc: Dict[str, Any]):
    if not doc:
        return doc
    doc = dict(doc)
    if "_id" in doc:
        doc["id"] = str(doc.pop("_id"))
    # Convert nested ObjectIds
    for k, v in list(doc.items()):
        if isinstance(v, ObjectId):
            doc[k] = str(v)
        if isinstance(v, list):
            doc[k] = [str(x) if isinstance(x, ObjectId) else x for x in v]
    return doc

# ---------------------- Health ----------------------
@app.get("/")
def root():
    return {"message": "DreamNest API running"}

@app.get("/schema")
def schema():
    return SCHEMA_MANIFEST.model_dump()

@app.get("/test")
def test_database():
    response = {
        "backend": "✅ Running",
        "database": "❌ Not Available",
        "database_url": None,
        "database_name": None,
        "connection_status": "Not Connected",
        "collections": []
    }
    try:
        if db is not None:
            response["database"] = "✅ Available"
            response["database_url"] = "✅ Set" if os.getenv("DATABASE_URL") else "❌ Not Set"
            response["database_name"] = db.name
            response["connection_status"] = "Connected"
            try:
                collections = db.list_collection_names()
                response["collections"] = collections[:10]
                response["database"] = "✅ Connected & Working"
            except Exception as e:
                response["database"] = f"⚠️  Connected but Error: {str(e)[:80]}"
        else:
            response["database"] = "⚠️  Available but not initialized"
    except Exception as e:
        response["database"] = f"❌ Error: {str(e)[:80]}"
    return response

# ---------------------- Catalog ----------------------
@app.get("/api/catalog")
def get_catalog():
    communities = [to_serializable(x) for x in get_documents("community")]
    towers = [to_serializable(x) for x in get_documents("tower")]
    flats = [to_serializable(x) for x in get_documents("flat")]
    floorplans = [to_serializable(x) for x in get_documents("floorplan")]
    return {
        "communities": communities,
        "towers": towers,
        "flats": flats,
        "floorplans": floorplans,
    }

# ---------------------- Create content (admin) ----------------------
# Minimal creation endpoints to seed data quickly
@app.post("/api/communities")
def create_community(payload: Community):
    new_id = create_document("community", payload)
    return {"id": new_id}

@app.post("/api/towers")
def create_tower(payload: Tower):
    new_id = create_document("tower", payload)
    return {"id": new_id}

@app.post("/api/flats")
def create_flat(payload: Flat):
    new_id = create_document("flat", payload)
    return {"id": new_id}

@app.post("/api/floorplans")
def create_floorplan(payload: FloorPlan):
    new_id = create_document("floorplan", payload)
    return {"id": new_id}

# ---------------------- Leads ----------------------
class LeadRequest(BaseModel):
    name: str
    phone: str
    email: Optional[str] = None
    project_id: Optional[str] = None
    requirement_type: Optional[str] = None
    source: Optional[str] = None

@app.post("/api/leads")
def create_lead(payload: LeadRequest):
    lead = Lead(
        name=payload.name,
        phone=payload.phone,
        email=payload.email,
        requirement_type=payload.requirement_type or "Interior",
        source=payload.source or "web",
        status="New",
        assigned_manager_id=None,
        assigned_agent_id=None,
        follow_up_ids=[],
    )
    new_id = create_document("lead", lead)
    return {"id": new_id, "status": "New"}

@app.get("/api/leads")
def list_leads(assigned_to: Optional[str] = None):
    filt: Dict[str, Any] = {}
    if assigned_to:
        # return leads where assigned_agent_id == assigned_to OR assigned_manager_id == assigned_to
        filt = {"$or": [{"assigned_agent_id": assigned_to}, {"assigned_manager_id": assigned_to}]}
    leads = db["lead"].find(filt).sort("created_at", -1)
    return [to_serializable(x) for x in leads]

class LeadUpdate(BaseModel):
    status: Optional[str] = None
    assigned_agent_id: Optional[str] = None
    assigned_manager_id: Optional[str] = None

@app.patch("/api/leads/{lead_id}")
def update_lead(lead_id: str, payload: LeadUpdate):
    if not ObjectId.is_valid(lead_id):
        raise HTTPException(status_code=400, detail="Invalid lead id")
    update_doc = {k: v for k, v in payload.model_dump(exclude_none=True).items()}
    if not update_doc:
        return {"updated": False}
    res = db["lead"].update_one({"_id": ObjectId(lead_id)}, {"$set": update_doc})
    if res.matched_count == 0:
        raise HTTPException(status_code=404, detail="Lead not found")
    return {"updated": True}

# ---------------------- Follow-ups ----------------------
@app.post("/api/followups")
def create_followup(payload: FollowUp):
    # ensure lead exists
    if not ObjectId.is_valid(payload.lead_id):
        raise HTTPException(status_code=400, detail="Invalid lead id")
    exists = db["lead"].find_one({"_id": ObjectId(payload.lead_id)})
    if not exists:
        raise HTTPException(status_code=404, detail="Lead not found")
    new_id = create_document("followup", payload)
    # push to lead.follow_up_ids
    db["lead"].update_one({"_id": ObjectId(payload.lead_id)}, {"$push": {"follow_up_ids": new_id}})
    return {"id": new_id}

@app.get("/api/followups/{lead_id}")
def list_followups(lead_id: str):
    if not ObjectId.is_valid(lead_id):
        raise HTTPException(status_code=400, detail="Invalid lead id")
    items = db["followup"].find({"lead_id": lead_id}).sort("created_at", -1)
    return [to_serializable(x) for x in items]

# ---------------------- Quotations ----------------------
@app.post("/api/quotations/compute")
def compute_quote(inputs: QuotationInputs):
    subtotal = inputs.area * inputs.rate_per_sqft + inputs.material_cost
    gst = subtotal * (inputs.gst_percent / 100.0)
    total_with_gst = subtotal + gst
    markup = total_with_gst * (inputs.markup_percent / 100.0)
    grand_total = round(total_with_gst + markup, 2)
    return {
        "subtotal": round(subtotal, 2),
        "gst": round(gst, 2),
        "markup": round(markup, 2),
        "total": grand_total,
    }

class QuotationCreate(BaseModel):
    lead_id: str
    project_id: Optional[str] = None
    inputs: QuotationInputs
    created_by: Optional[str] = None

@app.post("/api/quotations")
def create_quote(payload: QuotationCreate):
    if not ObjectId.is_valid(payload.lead_id):
        raise HTTPException(status_code=400, detail="Invalid lead id")
    res = compute_quote(payload.inputs)
    quotation = Quotation(
        lead_id=payload.lead_id,
        project_id=payload.project_id,
        pricing_inputs=payload.inputs,
        generated_price=res["total"],
        created_by=payload.created_by,
        pdf_url=None,
    )
    new_id = create_document("quotation", quotation)
    return {"id": new_id, "total": res["total"]}

@app.get("/api/quotations/by-lead/{lead_id}")
def quotes_by_lead(lead_id: str):
    if not ObjectId.is_valid(lead_id):
        raise HTTPException(status_code=400, detail="Invalid lead id")
    items = db["quotation"].find({"lead_id": lead_id}).sort("created_at", -1)
    return [to_serializable(x) for x in items]


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
