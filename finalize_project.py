#!/usr/bin/env python3
"""
finalize_project.py -- Implements Auto-Invoicing, Nuke script, and Dockerization.
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

ROOT = Path.cwd()
if not (ROOT / "manage.py").exists():
    sys.exit("Run this from inside the opd/ directory")

PY = ROOT / ".venv" / ("Scripts" if sys.platform == "win32" else "bin") / (
    "python.exe" if sys.platform == "win32" else "python"
)
if not PY.exists():
    PY = Path(sys.executable)

ENV = os.environ.copy()
ENV.setdefault("DB_NAME", "opd")
ENV.setdefault("DB_USER", "opd_owner")
ENV.setdefault("DB_PASSWORD", "opd_owner")


def sh(*cmd):
    print("   $", " ".join(str(c) for c in cmd))
    subprocess.run([str(c) for c in cmd], check=True, env=ENV)


def write(rel: str, content: str):
    p = ROOT / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content, encoding="utf-8")
    print(f"   wrote {rel}")


# ═══════════════════════════════════════════════════════════════════════
# TASK 1: AUTO-INVOICE ON VISIT CLOSE
# ═══════════════════════════════════════════════════════════════════════
print("\n=== [1/3] Implementing Auto-Invoice ===")

# 1a. Add base_price to LabTest and Medicine
bp = ROOT / "lab" / "models.py"
b = bp.read_text(encoding="utf-8")
if "base_price" not in b:
    b = b.replace(
        "    is_active = models.BooleanField(default=True)",
        "    is_active = models.BooleanField(default=True)\n"
        "    base_price = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)"
    )
    bp.write_text(b, encoding="utf-8")
    print("   patched lab/models.py (base_price)")

pp = ROOT / "pharmacy" / "models.py"
p = pp.read_text(encoding="utf-8")
if "base_price" not in p:
    p = p.replace(
        "    is_active = models.BooleanField(default=True)",
        "    is_active = models.BooleanField(default=True)\n"
        "    base_price = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)"
    )
    pp.write_text(p, encoding="utf-8")
    print("   patched pharmacy/models.py (base_price)")

# 1b. Visit Signals
write("visits/signals.py", '''\
from decimal import Decimal
from django.db.models.signals import pre_save, post_save
from django.dispatch import receiver
from billing.models import Invoice, InvoiceItem
from .models import Visit

@receiver(pre_save, sender=Visit)
def track_previous_status(sender, instance, **kwargs):
    if instance.pk:
        old = Visit.all_objects.get(pk=instance.pk)
        instance._previous_status = old.status
    else:
        instance._previous_status = None

@receiver(post_save, sender=Visit)
def auto_generate_invoice(sender, instance, created, **kwargs):
    # Trigger only when transitioning TO closed
    if created or instance.status != Visit.Status.CLOSED:
        return
    
    prev = getattr(instance, "_previous_status", None)
    if prev == Visit.Status.CLOSED:
        return

    # Don't duplicate if an invoice already exists
    if Invoice.all_objects.filter(visit=instance).exists():
        return

    with db_tenant_context(instance.tenant):
        inv = Invoice.objects.create(
            visit=instance,
            patient=instance.patient,
            status=Invoice.Status.DRAFT,
            currency="ZMW",
        )
        
        # Add consultation fee (base assumption)
        InvoiceItem.objects.create(
            invoice=inv, category=InvoiceItem.Category.CONSULTATION,
            description="OPD Consultation", quantity=1, unit_price=Decimal("150.00")
        )

        # Pull from Orders
        for order in instance.orders.all():
            for item in order.items.all():
                if order.kind == "lab":
                    from lab.models import LabTest
                    test = LabTest.objects.filter(code=item.code).first()
                    price = test.base_price if test else Decimal("0.00")
                    InvoiceItem.objects.create(
                        invoice=inv, category=InvoiceItem.Category.LAB,
                        description=item.description, quantity=item.quantity,
                        unit_price=price, order_item_code=item.code
                    )
                elif order.kind == "radiology":
                    InvoiceItem.objects.create(
                        invoice=inv, category=InvoiceItem.Category.RADIOLOGY,
                        description=item.description, quantity=item.quantity,
                        unit_price=Decimal("120.00"), order_item_code=item.code
                    )
                elif order.kind == "pharmacy":
                    from pharmacy.models import Medicine
                    med = Medicine.objects.filter(code=item.code).first()
                    price = med.base_price if med else Decimal("0.00")
                    InvoiceItem.objects.create(
                        invoice=inv, category=InvoiceItem.Category.PHARMACY,
                        description=item.description, quantity=item.quantity,
                        unit_price=price, order_item_code=item.code
                    )
                    
        inv.recalculate()
''')

# 1c. Register signals in visits/apps.py
va = ROOT / "visits" / "apps.py"
v = va.read_text(encoding="utf-8")
if "signals" not in v:
    v = v.replace(
        "    name = \"visits\"",
        "    name = \"visits\"\n\n    def ready(self):\n        import visits.signals  # noqa"
    )
    va.write_text(v, encoding="utf-8")

# 1d. Migrate
print("==> Migrations for base_price")
sh(PY, "manage.py", "makemigrations", "lab", "pharmacy")
sh(PY, "manage.py", "migrate")


# ═══════════════════════════════════════════════════════════════════════
# TASK 2: NUKE & REBUILD SCRIPT
# ═══════════════════════════════════════════════════════════════════════
print("\n=== [2/3] Creating reset_project.py ===")
write("reset_project.py", '''\
#!/usr/bin/env python3
"""
reset_project.py -- Nuke the DB and rebuild from scratch.
Use --drop to completely drop and recreate the PostgreSQL database.
"""
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PY = ROOT / ".venv" / ("Scripts" if sys.platform == "win32" else "bin") / (
    "python.exe" if sys.platform == "win32" else "python"
)
if not PY.exists():
    PY = Path(sys.executable)

ENV = os.environ.copy()
ENV.setdefault("DB_NAME", "opd")
ENV.setdefault("DB_USER", "opd_owner")
ENV.setdefault("DB_PASSWORD", "opd_owner")

def sh(*cmd):
    subprocess.run([str(c) for c in cmd], check=True, env=ENV)

def main():
    if "--drop" in sys.argv:
        print("==> Dropping and recreating database 'opd'...")
        # Connect to 'postgres' db to drop 'opd'
        env_drop = ENV.copy()
        env_drop["DB_NAME"] = "postgres"
        sql = f"DROP DATABASE IF EXISTS {ENV['DB_NAME']}; CREATE DATABASE {ENV['DB_NAME']} OWNER {ENV['DB_USER']};"
        subprocess.run(
            ["psql", "-U", ENV["DB_USER"], "-d", "postgres", "-c", sql],
            env=env_drop, check=True
        )
    else:
        print("==> Flushing database (truncating all tables)...")
        sh(PY, "manage.py", "flush", "--no-input")

    print("==> Applying migrations...")
    sh(PY, "manage.py", "migrate")

    print("==> Seeding demo data...")
    sh(PY, "manage.py", "seed_demo", "--reset")

    print("==> Done! Run 'python manage.py runserver' to start.")

if __name__ == "__main__":
    main()
''')


# ═══════════════════════════════════════════════════════════════════════
# TASK 3: DOCKERIZE
# ═══════════════════════════════════════════════════════════════════════
print("\n=== [3/3] Dockerizing ===")

# 3a. requirements.txt
write("requirements.txt", '''\
Django>=6.1,<6.2
psycopg[binary]>=3.1
djangorestframework>=3.15
djangorestframework-simplejwt>=5.3
drf-spectacular>=0.27
Pillow>=10.0
cryptography>=42.0
celery>=5.3
redis>=5.0
''')

# 3b. Dockerfile
write("Dockerfile", '''\
FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# Install system dependencies for psycopg2 and Pillow
RUN apt-get update && apt-get install -y \\
    gcc libpq-dev python3-dev \\
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Expose port for the web server
EXPOSE 8000

# Default command (overridden in docker-compose for celery)
CMD ["python", "manage.py", "runserver", "0.0.0.0:8000"]
''')

# 3c. init.sql (For Docker Postgres setup)
write("init.sql", '''\
-- Create the app role (non-owner for RLS enforcement)
CREATE ROLE opd_app LOGIN PASSWORD 'opd_app';
GRANT USAGE ON SCHEMA public TO opd_app;
ALTER DEFAULT PRIVILEGES FOR ROLE opd_owner IN SCHEMA public
    GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO opd_app;
ALTER DEFAULT PRIVILEGES FOR ROLE opd_owner IN SCHEMA public
    GRANT USAGE, SELECT ON SEQUENCES TO opd_app;
''')

# 3d. docker-compose.yml
write("docker-compose.yml", '''\
version: "3.9"

services:
  db:
    image: postgres:16-alpine
    environment:
      POSTGRES_DB: opd
      POSTGRES_USER: opd_owner
      POSTGRES_PASSWORD: opd_owner
    volumes:
      - postgres_data:/var/lib/postgresql/data
      - ./init.sql:/docker-entrypoint-initdb.d/init.sql
    ports:
      - "5432:5432"

  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"

  web:
    build: .
    command: >
      sh -c "python manage.py migrate &&
             python manage.py seed_demo --reset &&
             python manage.py runserver 0.0.0.0:8000"
    volumes:
      - .:/app
    ports:
      - "8000:8000"
    environment:
      - DB_HOST=db
      - DB_NAME=opd
      - DB_USER=opd_app
      - DB_PASSWORD=opd_app
      - REDIS_URL=redis://redis:6379/0
      - DJANGO_DEBUG=1
    depends_on:
      - db
      - redis

  worker:
    build: .
    command: celery -A config worker -l info --pool=solo
    volumes:
      - .:/app
    environment:
      - DB_HOST=db
      - DB_NAME=opd
      - DB_USER=opd_owner   # Worker runs migrations or needs bypass sometimes, owner is safer for raw tasks
      - DB_PASSWORD=opd_owner
      - REDIS_URL=redis://redis:6379/0
    depends_on:
      - db
      - redis

volumes:
  postgres_data:
''')

# 3e. Ensure static/media dirs exist for Docker volume mapping
(ROOT / "static").mkdir(exist_ok=True)
(ROOT / "media").mkdir(exist_ok=True)
print("   created static/ and media/ directories")

# ─── Final Check ───────────────────────────────────────────────────────
print("\n==> manage.py check")
sh(PY, "manage.py", "check")

print("\n==> ALL DONE! You now have Auto-Invoicing, a Reset script, and Docker.")