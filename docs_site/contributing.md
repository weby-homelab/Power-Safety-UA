# Contributing

Дякуємо за інтерес до **Power-Safety-UA**! Ми вітаємо внески, що покращують
надійність моніторингу, безпеку та досвід розробки.

## Code of Conduct

Будьте ввічливими та конструктивними у спілкуванні.

## Як зробити внесок

1. **Опишіть зміну** — відкрийте Issue (мітки `bug`, `enhancement`,
   `documentation`).
2. **Створіть гілку:**
   ```bash
   git checkout -b feature/your-feature-name
   ```
3. **Реалізуйте зміни** та запустіть тести й лінтинг.
4. **Підпишіть коміти** GPG-ключем:
   ```bash
   git commit -S -m "Описовий повідомлення коміту"
   ```
5. **Відкрийте Pull Request** у `main`.

## Локальний запуск тестів

```bash
PYTHONPATH=. pytest tests/ -v
```

CI перевіряє: Ruff (format + lint), Bandit (SAST), Trivy (CVE), pytest з
покриттям ≥ 35%.

## Docker-вимоги

- Multi-stage build.
- Не запускайте контейнер від root (`USER appuser`).
- Тримайте порти конфігурованими через `.env`.

Повний опис — у [CONTRIBUTING.md](https://github.com/weby-homelab/Power-Safety-UA/blob/main/CONTRIBUTING.md).
