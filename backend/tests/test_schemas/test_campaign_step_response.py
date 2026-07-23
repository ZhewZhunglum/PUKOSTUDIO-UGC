import uuid
from types import SimpleNamespace

from app.schemas.campaign import CampaignStepResponse
from app.schemas.client_campaign import ClientCampaignStepResponse


def _orm_step(attachment_ids):
    return SimpleNamespace(
        id=uuid.uuid4(),
        step_order=1,
        step_type="initial",
        template_id=uuid.uuid4(),
        delay_days=0,
        condition=None,
        attachment_ids=attachment_ids,
    )


def test_campaign_step_response_coerces_null_attachment_ids_to_empty_list():
    # Steps created before the attachment_ids column existed have NULL in the
    # DB, not an empty JSONB array — the response model must not 500 on them.
    response = CampaignStepResponse.model_validate(_orm_step(None))
    assert response.attachment_ids == []


def test_client_campaign_step_response_coerces_null_attachment_ids_to_empty_list():
    response = ClientCampaignStepResponse.model_validate(_orm_step(None))
    assert response.attachment_ids == []
