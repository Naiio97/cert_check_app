# Nasazení aplikace — Evidence certifikátů

Tento dokument popisuje celý proces: od první instalace až po pravidelné aktualizace.

---

## Obsah

1. [Požadavky](#1-požadavky)
2. [První instalace](#2-první-instalace)
3. [Konfigurace IIS](#3-konfigurace-iis)
4. [Konfigurace aplikace (.env)](#4-konfigurace-aplikace-env)
5. [Aktualizace na novou verzi](#5-aktualizace-na-novou-verzi)
6. [Balení aplikace pro přenos](#6-balení-aplikace-pro-přenos-dev-pc)
7. [Řešení problémů](#7-řešení-problémů)

---

## 1. Požadavky

| Komponenta | Verze | Poznámka |
|---|---|---|
| Windows Server | 2016 / 2019 / 2022 | |
| IIS | 10+ | Role `Web Server (IIS)` |
| IIS URL Rewrite | 2.1+ | [Ke stažení od Microsoftu](https://www.iis.net/downloads/microsoft/url-rewrite) |
| Python | 3.12+ | Přidat do PATH při instalaci |
| wfastcgi nebo Waitress | — | Aplikace používá Waitress (součástí balíčku) |

> **Poznámka k internetu:** Server nemusí mít přístup na internet. Všechny Python závislosti jsou součástí balíčku (`dependencies/`).

---

## 2. První instalace

### 2.1 Příprava balíčku (na dev PC)

```bat
package.bat
```

Skript vytvoří soubor `certifikaty_deploy_YYYYMMDD_<git-hash>.zip`.

Zkopíruj ZIP na flash disk.

### 2.2 Instalace na serveru

1. **Vytvoř složku** pro aplikaci, např.:
   ```
   C:\inetpub\certifikaty\
   ```

2. **Rozbal ZIP** do této složky (pravé tlačítko → Extrahovat vše).

3. **Spusť PowerShell nebo CMD jako Administrator** a přejdi do složky:
   ```bat
   cd C:\inetpub\certifikaty
   ```

4. **Spusť instalaci:**
   ```bat
   deploy.bat
   ```

   Skript automaticky:
   - Vytvoří virtuální prostředí (`venv/`)
   - Nainstaluje závislosti offline z `dependencies/`
   - Vytvoří složky `logs/`, `uploads/`, `instance/`

5. **Vytvoř `.env` soubor** (viz [sekce 4](#4-konfigurace-aplikace-env)).

6. **Ověř funkčnost** spuštěním přímo z CMD:
   ```bat
   venv\Scripts\python.exe -m waitress --host=127.0.0.1 --port=8080 app:app
   ```
   Otevři `http://localhost:8080/evidence_certifikatu` — aplikace by měla odpovědět.
   Zastav pomocí `Ctrl+C` a pokračuj konfigurací IIS.

---

## 3. Konfigurace IIS

Aplikace běží jako Python WSGI proces (Waitress) na portu 8080. IIS slouží jako **reverse proxy**.

### 3.1 Vytvoření Application Poolu

1. Otevři **IIS Manager** (`inetmgr`)
2. **Application Pools** → **Add Application Pool**
   - Name: `CertifikátyPool` *(libovolný název, zapamatuj si ho)*
   - .NET CLR version: **No Managed Code**
   - Managed pipeline mode: **Integrated**
3. Klikni na pool → **Advanced Settings**:
   - **Identity**: `ApplicationPoolIdentity` (nebo dedikovaný servisní účet)
   - **Start Mode**: `AlwaysRunning`
   - **Idle Time-out**: `0` (zakáže automatické zastavení)

### 3.2 Vytvoření webu / aplikace

1. **Sites** → **Add Website** (nebo přidej jako aplikaci pod existující web)
   - Site name: `Certifikáty`
   - Application pool: `CertifikátyPool`
   - Physical path: `C:\inetpub\certifikaty`
   - Port: `80` (nebo jiný)

### 3.3 Nastavení reverse proxy (URL Rewrite + ARR)

Ujisti se, že je nainstalován **Application Request Routing (ARR)** a **URL Rewrite**.

Vytvoř soubor `C:\inetpub\certifikaty\web.config`:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<configuration>
  <system.webServer>
    <rewrite>
      <rules>
        <rule name="Proxy to Waitress" stopProcessing="true">
          <match url="(.*)" />
          <action type="Rewrite" url="http://127.0.0.1:8080/{R:1}" />
        </rule>
      </rules>
    </rewrite>
  </system.webServer>
</configuration>
```

### 3.4 Spuštění Waitress jako Windows Service

Aby aplikace běžela na pozadí (i po restartu serveru), použij **NSSM** (Non-Sucking Service Manager).

1. Stáhni NSSM: https://nssm.cc/download a zkopíruj `nssm.exe` na server.

2. Spusť CMD jako Administrator:
   ```bat
   nssm install CertifikátyApp
   ```

3. V GUI nastav:
   - **Path:** `C:\inetpub\certifikaty\venv\Scripts\python.exe`
   - **Arguments:** `-m waitress --host=127.0.0.1 --port=8080 app:app`
   - **Startup directory:** `C:\inetpub\certifikaty`
   - Záložka **Environment:** přidej `FLASK_ENV=production`

4. Spusť službu:
   ```bat
   nssm start CertifikátyApp
   ```

> **Alternativa bez NSSM:** Nastav v IIS Application Pool **Process Model → Start Mode: AlwaysRunning** a použij `wfastcgi`. NSSM je ale jednodušší.

---

## 4. Konfigurace aplikace (.env)

Vytvoř soubor `.env` ve složce aplikace (`C:\inetpub\certifikaty\.env`).  
Tento soubor **nikdy nezahrnutý do balíčku** — obsahuje citlivé údaje a přetrvává mezi aktualizacemi.

```env
# Bezpečnost
SECRET_KEY=změň-na-náhodný-řetězec-min-32-znaků

# SMTP (email notifikace)
MAIL_SERVER=smtp.firma.cz
MAIL_PORT=25
MAIL_USE_TLS=false
MAIL_USERNAME=
MAIL_PASSWORD=
MAIL_SENDER_ADDRESS=certifikaty@firma.cz
MAIL_SENDER_NAME=Evidence certifikátů
MAIL_SUBJECT_PREFIX=[Certifikáty]
MAIL_RECIPIENTS=admin@firma.cz,security@firma.cz

# Prostředí pro email reporty (live, uat, sit, prelive — nebo kombinace)
REPORT_ENVS=live

# Den v měsíci pro měsíční report (1 = první den v měsíci)
REPORT_DAY=1
REPORT_HOUR=9
REPORT_MINUTE=0
```

> **Tip:** `SECRET_KEY` vygeneruj takto:
> ```bat
> venv\Scripts\python.exe -c "import secrets; print(secrets.token_hex(32))"
> ```

---

## 5. Aktualizace na novou verzi

Toto je nejčastější operace. Celý proces trvá cca **2 minuty**.

### Na dev PC

```bat
package.bat
```

→ vytvoří `certifikaty_deploy_20260415_a1b2c3d.zip`

Zkopíruj ZIP na flash disk.

### Na serveru

1. Zkopíruj ZIP do složky aplikace (`C:\inetpub\certifikaty\`)

2. Spusť **CMD jako Administrator**:

```bat
cd C:\inetpub\certifikaty
update.bat CertifikátyPool certifikaty_deploy_20260415_a1b2c3d.zip
```

*(Název app poolu viz IIS Manager → Application Pools)*

Skript automaticky provede:
| Krok | Co se stane |
|---|---|
| 1 | Zastaví IIS Application Pool |
| 2 | Extrahuje ZIP přes stávající soubory |
| 3 | Nainstaluje nové/aktualizované závislosti |
| 4 | Spustí IIS Application Pool |

**Co se NIKDY nepřepíše:**

| Složka / soubor | Obsah |
|---|---|
| `instance/` | Databáze (SQLite soubory) |
| `logs/` | Logy aplikace |
| `uploads/` | Nahrané soubory |
| `.env` | Konfigurace prostředí |

### Ověření po aktualizaci

Po dokončení skriptu:
1. Otevři aplikaci v prohlížeči
2. Zkontroluj zobrazenou verzi (nebo `VERSION.txt` ve složce aplikace)
3. Zkontroluj logy: `logs\app.log`

---

## 6. Balení aplikace pro přenos (dev PC)

```bat
package.bat
```

**Co balíček obsahuje:**

```
certifikaty_deploy_YYYYMMDD_<hash>.zip
├── app/                  kód aplikace
├── static/               CSS, JS, obrázky
├── dependencies/         offline Python balíčky
├── app.py                vstupní bod
├── config.py             konfigurace
├── requirements.txt      seznam závislostí
├── deploy.bat            první instalace
├── update.bat            aktualizace
└── VERSION.txt           git hash + datum sestavení
```

**Co balíček NEobsahuje** (záměrně):
- `instance/` — databáze
- `logs/` — logy
- `uploads/` — nahrané soubory
- `.env` — konfigurace s hesly
- `venv/` — virtuální prostředí (generuje se na serveru)

---

## 7. Řešení problémů

### Aplikace nereaguje po update

```bat
# Zkontroluj stav app poolu
C:\Windows\System32\inetsrv\appcmd.exe list apppool CertifikátyPool

# Ruční restart
C:\Windows\System32\inetsrv\appcmd.exe stop apppool /apppool.name:"CertifikátyPool"
C:\Windows\System32\inetsrv\appcmd.exe start apppool /apppool.name:"CertifikátyPool"
```

### Chyba při spuštění aplikace

```bat
# Spusť ručně a sleduj výstup
cd C:\inetpub\certifikaty
venv\Scripts\python.exe app.py
```

Chybová hláška se vypíše přímo do konzole.

### Chybějící tabulky v databázi

Při prvním startu s novou databází aplikace vytvoří tabulky automaticky.  
Pokud databáze existuje ale tabulky chybí:
```bat
venv\Scripts\python.exe -c "from app import create_app, db; app = create_app(); app.app_context().push(); db.create_all()"
```

### Migrace dat z UAT (přejmenování z Test)

Pokud existuje stará databáze `instance\certifikaty_test.db` z doby před přejmenováním prostředí:
```bat
copy instance\certifikaty_test.db instance\certifikaty_uat.db
```

### Logy

Aplikační logy se ukládají do `logs\app.log` s automatickou rotací.  
Starší logy jsou archivovány jako `logs\app.log.YYYY-MM-DD.zip`.

---

*Dokument aktualizován: 2026-04-15*
