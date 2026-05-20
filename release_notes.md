# Release v3.4.12

**Deep Security Hardening (Removing krb5 & curl, Python-Native Healthcheck)**
В цьому релізі повністю ліквідовано всі вразливості пакетів `krb5` шляхом повного видалення некурсованих системних бібліотек Kerberos та утиліти `curl` з підсумкового образу.

## Що нового / What's New:
🇺🇦 **Українська:**
- Повністю видалено пакети `libkrb5-3`, `libgssapi-krb5-2`, `libkrb5support0` та `libk5crypto3` (разом з їхніми залежностями), що ліквідувало 5 вразливостей (включаючи `CVE-2026-40355`, `CVE-2026-40356` тощо).
- Видалено системну утиліту `curl` та `libcurl4`, що усунуло додаткові потенційні вектори вразливостей.
- Переписано `HEALTHCHECK` на використання чистих стандартних бібліотек Python (`urllib.request`), тому робота моніторингу працездатності контейнера не змінилася та не потребує зовнішніх утиліт.

🇬🇧 **English:**
- Fully purged `libkrb5-3`, `libgssapi-krb5-2`, `libkrb5support0`, and `libk5crypto3` packages, eliminating all Kerberos vulnerabilities.
- Removed system utilities `curl` and `libcurl4` to minimize attack surface.
- Replaced container `HEALTHCHECK` command with a native Python script using `urllib.request`.
