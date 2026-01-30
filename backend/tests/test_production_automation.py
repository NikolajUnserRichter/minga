
import pytest
from datetime import date, timedelta
from app.models.forecast import ProductionSuggestion, SuggestionStatus
from app.models.production import GrowBatch, GrowBatchStatus
from app.models.seed import SeedBatch
from app.schemas.forecast import ProductionSuggestionApprove

@pytest.mark.asyncio
async def test_approve_suggestion_creates_grow_batch(client, db_session, seed_factory, seed_batch_factory, forecast_factory):
    # 1. Setup Data
    seed = seed_factory(name="Test Radish")
    # Active SeedBatch
    seed_batch = seed_batch_factory(seed=seed, menge_gramm=1000, verbleibend_gramm=500)
    
    forecast = forecast_factory(seed=seed, datum=date.today() + timedelta(days=14))
    
    suggestion = ProductionSuggestion(
        forecast_id=forecast.id,
        seed_id=seed.id,
        empfohlene_trays=10,
        aussaat_datum=date.today(),
        erwartete_ernte_datum=date.today() + timedelta(days=10),
        status=SuggestionStatus.VORGESCHLAGEN
    )
    db_session.add(suggestion)
    db_session.commit()
    db_session.refresh(suggestion)
    
    # 2. Approve via API
    response = client.post(
        f"/api/v1/forecasting/production-suggestions/{suggestion.id}/approve",
        json={"angepasste_trays": 12}  # Override trays
    )
    
    # 3. Verify Response
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "GENEHMIGT"
    assert data["empfohlene_trays"] == 12
    assert "generated_batch_id" in data
    batch_id = data["generated_batch_id"]
    assert batch_id is not None
    
    # 4. Verify GrowBatch created in DB
    grow_batch = db_session.get(GrowBatch, batch_id)
    assert grow_batch is not None
    assert grow_batch.seed_batch_id == seed_batch.id
    assert grow_batch.tray_anzahl == 12
    assert grow_batch.status == GrowBatchStatus.KEIMUNG
    assert "Automatisch erstellt" in grow_batch.notizen
