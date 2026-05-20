# Release v3.4.13

**Maximum Security Hardening (Purged tar / CVE-2025-45582 Remediation)**
В цьому релізі досягнуто найвищого рівня безпеки образу шляхом примусового видалення системної утиліти `tar` та її метаданих, що ліквідувало останню вразливість `CVE-2025-45582`.

## Що нового / What's New:
🇺🇦 **Українська:**
- Завдяки інструкції `dpkg --force-all --purge tar` з образу повністю видалено утиліту `tar`, яка мала вразливість середньої важливості `CVE-2025-45582`.
- Оскільки додаток є веб-сервісом моніторингу і не виконує операцій архівування/розархівування, відсутність `tar` жодним чином не впливає на працездатність програми в рантаймі.
- Тепер у підсумковому образі **повністю відсутні** будь-які медіум/хай/крітікал CVE.

🇬🇧 **English:**
- Completely purged the `tar` package and its metadata from the container using `dpkg --force-all --purge tar`, mitigating the remaining `CVE-2025-45582` vulnerability.
- As the application is a monitoring service and doesn't unpack untrusted files, the absence of `tar` has zero impact on runtime behavior.
- The image is now free of any Medium, High, or Critical CVEs.
