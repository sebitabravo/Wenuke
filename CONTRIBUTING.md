# Contribuir a Werken-mapu

## Setup rápido

```bash
git clone https://github.com/sebitabravo/Wenuke.git
cd Wenuke/backend
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
uvicorn main:app --reload --port 8000
```

El sistema funciona sin configurar nada — usa SQLite local y responde offline con reglas expertas.

## Antes de abrir un PR

- Tests pasan: `pytest -v`
- Lint limpio: `ruff check .`
- Tipos OK: `mypy . --ignore-missing-imports --follow-imports=skip`
- Formato: `ruff format .`

## Convenciones

- **Commits:** [Conventional Commits](https://www.conventionalcommits.org/) — `feat(scope):`, `fix(scope):`, `refactor(scope):`, `test:`, `docs:`
- **Código:** Python 3.12+, type hints en funciones públicas, docstrings en español
- **Tests:** unit tests para dominio (`reglas.py`, `clima.py`), E2E para API

## Reportar bugs

Abrir un issue con:
- Endpoint o feature afectada
- Request/response esperado vs real
- Steps to reproduce

## Arquitectura

`reglas.py` es el core del dominio — cero I/O, completamente testeado. Toda la lógica agronómica vive ahí. Las APIs externas (clima, IA, precios, WhatsApp) son clientes async que el dominio consume pero no conoce.
