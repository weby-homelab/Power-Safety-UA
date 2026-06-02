# Release v3.5.0

**Settings, Dashboard and AQI Enhancements**

## Що нового / What's New:
🇺🇦 **Українська:**
- **Виправлення адмін панелі:** Виправлено зміну ID Станції SaveEcoBot (наприклад, 13992) для коректного збереження та відображення даних якості повітря на дашборді.
- **Пріоритет джерел:** Виправлено застосування пріоритету джерел (GitHub/ДТЕК vs Yasno). ДТЕК тепер коректно відображається та використовується за пріоритетом.
- **Покращення дашборду:** Напис про наступне планове відключення тепер коректно показує "Відключення не плануються 🔆" (замість "невідомий час 🤷‍♂️"), коли світло є і відключень немає в графіку.
- **Якість повітря (AQI):** Додано четверту смужку показника якості повітря AQI (зелений, жовтий, червоний) на денні та тижневі графіки.
- **Статистика тривог:** У тижневі звіти в Telegram додано детальну інформацію про кількість тривог, їх сумарну тривалість та відсоток від тижневого часу.

🇬🇧 **English:**
- **Admin Panel Fixes:** Fixed SaveEcoBot station ID updates (e.g. 13992) to correctly save and load air quality data.
- **Source Priority:** Fixed the application of source priority (GitHub/DTEK vs Yasno). The dashboard now correctly shows DTEK when prioritized.
- **Dashboard Text Fix:** Correctly displays "Outages not planned 🔆" instead of "unknown time 🤷‍♂️" when power is ON and no outages are scheduled.
- **Air Quality (AQI) Strip:** Added a fourth band representing AQI (Green, Yellow, Red) to daily and weekly report charts.
- **Air Raid Alerts Stats:** Included the weekly count, total duration, and percentage of air raid alerts in the weekly Telegram report caption.
