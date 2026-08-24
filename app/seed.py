from app.main import SessionLocal, Tenant, Widget, seed_tenant
from sqlalchemy import select


def seed_demo():
    with SessionLocal() as db:
        seed_tenant(db)
        tenant = db.scalar(select(Tenant))
        if not db.scalar(select(Widget).where(Widget.tenant_id == tenant.id)):
            db.add(Widget(id="demo-widget", tenant_id=tenant.id, name="Demo Lead Widget", title="Talk to us", fields_json='["name","email","message"]'))
            db.commit()


if __name__ == "__main__":
    seed_demo()
    print("Seeded demo tenant and widget. Token: demo-token-change-me")
