# Nasazení aplikace — Evidence certifikátů

Tento dokument popisuje celý proces: od první instalace na čistý server přes pravidelné aktualizace
až po migraci existující instalace (přejmenování TEST → UAT, přidání SIT a PRELIVE).

---

## Obsah

1. [Prostředí](#1-prostředí)
2. [Požadavky](#2-požadavky)
3. [Balení aplikace pro přenos (dev PC)](#3-balení-aplikace-pro-přenos-dev-pc)
4. [První instalace na novém serveru](#4-první-instalace-na-novém-serveru)
5. [Konfigurace IIS](#5-konfigurace-iis)
6. [Konfigurace aplikace (.env)](#6-konfigurace-aplikace-env)
7. [Aktualizace na novou verzi](#7-aktualizace-na-novou-verzi)
8. [Migrace existující instalace](#8-migrace-existující-instalace)
9. [Řešení problémů](#9-řešení-problémů)

---

## 1. Prostředí

Aplikace spravuje certifikáty napříč čtyřmi prostředími. Každé prostředí má vlastní SQLite databázi ve složce `instance/`.

| Prostředí | Soubor databáze              | Popis                              |
|-----------|------------------------------|------------------------------------|
| `live`    | `instance/certifikaty.db`    | Produkční data                     |
| `uat`     | `instance/certifikaty_uat.db`| User Acceptance Testing (dříve TEST) |
| `sit`     | `instance/certifikaty_sit.db`| System Integration Testing         |
| `prelive` | `instance/certifikaty_prelive.db` | Předprodukční prostředí       |

> **Poznámka:** Databázové soubory se **nikdy** neukládají do balíčku ani nepřepisují při aktualizaci.

---

## 2. Požadavky

| Komponenta         | Verze          | Poznámka                                        |
|--------------------|----------------|-------------------------------------------------|
| Windows Server     | 2016 / 2019 / 2022 |                                             |
| IIS                | 10+            | Role `Web Server (IIS)`                         |
| IIS URL Rewrite    | 2.1+           | Z offline instalátoru (součástí flash disku)    |
| ARR                | 3.0+           | Application Request Routing — pro reverse proxy |
| Python             | 3.12+          | Přidat do PATH při instalaci                    |
| NSSM               | 2.24+          | Non-Sucking Service Manager — pro Windows službu|

> **Internet není potřeba.** Všechny Python závislosti jsou součástí balíčku (`dependencies/`).

---

## 3. Balení aplikace pro přenos (dev PC)

Spusť na **dev PC** (kde máš přístup k internetu a repozitáři):

```bat
package.bat
```

Skript automaticky:
- Zapíše aktuální git hash do `VERSION.txt`
- Stáhne závislosti do `dependencies/` (offline pip install)
- Vytvoří ZIP: `certifikaty_deploy_YYYYMMDD_<git-hash>.zip`

**Co balíček obsahuje:**

```
certifikaty_deploy_YYYYMMDD_<hash>.zip
├── app/                  kód aplikace (Python moduly)
├── static/               CSS, JS, obrázky
├── dependencies/         offline Python balíčky (.whl)
├── wsgi.py               vstupní bod aplikace (waitress: wsgi:app)
├── config.py             konfigurace prostředí
├── requirements.txt      seznam závislostí
├── deploy.bat            první instalace
├── update.bat            aktualizace existující instalace
├── .env.example          vzor konfigurace
└── VERSION.txt           git hash + datum sestavení
```

**Co balíček NEobsahuje** (záměrně — tato data na serveru přetrvávají):

| Vynecháno     | Důvod                                      |
|---------------|--------------------------------------------|
| `instance/`   | Databáze — nesmí se přepsat               |
| `logs/`       | Logy aplikace                              |
| `uploads/`    | Nahrané soubory uživatelů                  |
| `.env`        | Konfigurace s hesly a citlivými údaji      |
| `venv/`       | Generuje se na serveru                     |

Zkopíruj ZIP na flash disk a přenes na server.

---

## 4. První instalace na novém serveru

### 4.1 Příprava složky

Vytvoř cílovou složku aplikace:

```
C:\inetpub\certifikaty\
```

### 4.2 Rozbalení balíčku

Zkopíruj ZIP z flash disku do `C:\inetpub\certifikaty\` a rozbal ho:
- Pravé tlačítko na ZIP → **Extrahovat vše** → cílová složka `C:\inetpub\certifikaty\`

### 4.3 Spuštění instalace

Spusť **CMD jako Administrator** a přejdi do složky:

```bat
cd C:\inetpub\certifikaty
deploy.bat
```

Skript provede:

| Krok | Co se stane                                                    |
|------|----------------------------------------------------------------|
| 1    | Ověří dostupnost Pythonu                                       |
| 2    | Vytvoří virtuální prostředí `venv/`                            |
| 3    | Nainstaluje závislosti offline z `dependencies/`               |
| 4    | Vytvoří složky `logs/`, `uploads/`, `instance/`                |
| 5    | Inicializuje všechny 4 databáze (live, uat, sit, prelive)      |

### 4.4 Vytvoření konfigurace

```bat
copy .env.example .env
notepad .env
```

Vyplň minimálně `SECRET_KEY` (viz [sekce 6](#6-konfigurace-aplikace-env)).

### 4.5 Ověření funkčnosti

Před konfigurací IIS ověř, že aplikace startuje:

```bat
cd C:\inetpub\certifikaty
venv\Scripts\python.exe -m waitress --host=0.0.0.0 --port=8080 wsgi:app
```

Otevři v prohlížeči: `http://localhost:8080/evidence_certifikatu`

Aplikace by měla odpovědět. Zastav ji pomocí `Ctrl+C` a pokračuj konfigurací IIS.

---

## 5. Konfigurace IIS

Aplikace běží jako Python WSGI proces (Waitress) na portu 8080. IIS slouží jako **reverse proxy**.

### 5.1 Vytvoření Application Poolu

1. Otevři **IIS Manager** (`inetmgr`)
2. **Application Pools** → **Add Application Pool**
   - Name: `CertifikátyPool` *(libovolný název, zapamatuj si ho pro update.bat)*
   - .NET CLR version: **No Managed Code**
   - Managed pipeline mode: **Integrated**
3. Klikni na pool → **Advanced Settings**:
   - **Identity**: `ApplicationPoolIdentity` (nebo dedikovaný servisní účet)
   - **Start Mode**: `AlwaysRunning`
   - **Idle Time-out**: `0` (zakáže automatické zastavení)

### 5.2 Vytvoření webu

1. **Sites** → **Add Website**
   - Site name: `Certifikáty`
   - Application pool: `CertifikátyPool`
   - Physical path: `C:\inetpub\certifikaty`
   - Port: `80` (nebo jiný)

### 5.3 Nastavení reverse proxy (URL Rewrite + ARR)

Ověř, že jsou nainstaleny **Application Request Routing (ARR)** a **URL Rewrite**.

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

### 5.4 Spuštění Waitress jako Windows Service (NSSM)

Aby aplikace běžela na pozadí i po restartu serveru, použij **NSSM**.

1. Zkopíruj `nssm.exe` z flash disku do `C:\inetpub\certifikaty\` (nebo do `C:\Windows\System32\`)

2. Spusť CMD jako Administrator:
   ```bat
   nssm install evidence_cert
   ```

3. V GUI nastav:
   - **Path:** `C:\inetpub\certifikaty\venv\Scripts\python.exe`
   - **Arguments:** `-m waitress --host=0.0.0.0 --port=8080 wsgi:app`
   - **Startup directory:** `C:\inetpub\certifikaty`
   - Záložka **Environment:** `FLASK_ENV=production`

4. Spusť službu:
   ```bat
   nssm start evidence_cert
   ```

5. Ověř, že služba běží:
   ```bat
   nssm status evidence_cert
   ```

> **Poznámka:** IIS Application Pool (`CertifikátyPool`) řídí IIS konfiguraci.
> Windows Service (`evidence_cert` přes NSSM) řídí samotný Python/Waitress proces.
> Obě věci musí běžet zároveň.

### 5.5 Logy služby (stdout/stderr) — rotace a úklid

Aplikační log (`logs\app.log`) rotuje a komprimuje aplikace sama. Stdout/stderr
procesu přesměrovává NSSM — nastav rotaci, ať soubory nerostou donekonečna:

```bat
nssm set evidence_cert AppStdout C:\inetpub\certifikaty\logs\service.out.log
nssm set evidence_cert AppStderr C:\inetpub\certifikaty\logs\service.err.log

REM Rotace: za běhu, 1× denně nebo po 10 MB (co nastane dřív)
nssm set evidence_cert AppRotateFiles 1
nssm set evidence_cert AppRotateOnline 1
nssm set evidence_cert AppRotateSeconds 86400
nssm set evidence_cert AppRotateBytes 10485760

nssm restart evidence_cert
```

Časové značky do těchto souborů doplňuje aplikace sama (každý řádek má prefix
`[YYYY-MM-DD HH:MM:SS]`), NSSM nic přidávat neumí.

NSSM staré rotované soubory nemaže. Úklid souborů starších 30 dní zajistí
naplánovaná úloha (spusť jednou jako Administrator):

```bat
schtasks /create /tn "Certifikaty_LogCleanup" /sc daily /st 03:00 /ru SYSTEM ^
  /tr "forfiles /p C:\inetpub\certifikaty\logs /m service*.log /d -30 /c \"cmd /c del @path\""
```

---

## 6. Konfigurace aplikace (.env)

Vytvoř soubor `.env` ve složce aplikace (`C:\inetpub\certifikaty\.env`).
Tento soubor **nikdy není součástí balíčku** — přetrvává mezi aktualizacemi.

```env
# ── Bezpečnost ────────────────────────────────────────────────────────────────
SECRET_KEY=změň-na-náhodný-řetězec-min-32-znaků

# ── Debug (pouze pro vývoj, NIKDY v produkci) ────────────────────────────────
FLASK_DEBUG=false

# ── SMTP (email notifikace) ───────────────────────────────────────────────────
MAIL_SERVER=smtp.firma.cz
MAIL_PORT=25
MAIL_USE_TLS=false
MAIL_SMTP_AUTH=false
MAIL_USERNAME=
MAIL_PASSWORD=
MAIL_SENDER_ADDRESS=certifikaty@firma.cz
MAIL_SENDER_NAME=Evidence certifikátů
MAIL_SUBJECT_PREFIX=[Certifikáty]
MAIL_RECIPIENTS=admin@firma.cz,security@firma.cz
# Odkaz pro tlačítko "Otevřít evidenci certifikátů" v e-mailech (prázdné = bez tlačítka)
APP_URL=https://server.firma.cz:8080/evidence_certifikatu

# ── Prostředí zahrnutá do měsíčního reportu ──────────────────────────────────
# Možné hodnoty: live, uat, sit, prelive  (odděleno čárkou, bez mezer)
REPORT_ENVS=live,uat,sit,prelive

# ── Plán měsíčního reportu ────────────────────────────────────────────────────
REPORT_DAY=1      # den v měsíci (1-28)
REPORT_HOUR=9     # hodina (0-23)
REPORT_MINUTE=0   # minuta (0-59)
```

> **Poznámka k reportům:** Hodnoty v `.env` jsou jen výchozí. Plán reportů se
> primárně nastavuje přímo v aplikaci (**Nastavení → Měsíční reporty**) a uloží
> se do databáze — hodnoty z DB mají přednost a změna se aplikuje bez restartu.
> Každé další prostředí se odesílá s odstupem 5 minut. Pokud byla aplikace
> v plánovaném čase mimo provoz (typicky měsíční patching), report se odešle
> dodatečně automaticky po startu služby — nikdy ale ne před plánovaným časem.

**Vygenerování SECRET_KEY:**

```bat
venv\Scripts\python.exe -c "import secrets; print(secrets.token_hex(32))"
```

**Alternativa — konfigurace přes XML:**

Pokud chceš SMTP načíst ze sdíleného XML souboru:

```env
MAIL_CONFIG_XML=C:\shared\config\mail_config.xml
```

Očekávaná struktura XML:
```xml
<configuration>
  <mail>
    <host>smtp.firma.cz</host>
    <port>25</port>
    <username></username>
    <password></password>
    <smtpAuth>false</smtpAuth>
    <startTlsEnabled>false</startTlsEnabled>
    <senderAddress>certifikaty@firma.cz</senderAddress>
    <senderName>Evidence certifikátů</senderName>
    <subject>[Certifikáty]</subject>
  </mail>
</configuration>
```

---

## 7. Aktualizace na novou verzi

Toto je nejčastější operace. Celý proces trvá **cca 2–3 minuty**.

### Architektura IIS deploymentu

```
Uživatel → IIS (port 80) → URL Rewrite (reverse proxy) → Waitress (port 8080) → Python app
             └── App Pool                                    └── NSSM služba
```

**Při aktualizaci musí být zastaven Waitress (NSSM služba)**, jinak má Python soubory
zamčené a nový kód by se nenačetl. IIS pool se zastaví, aby nepřijímal requesty v době výpadku.

### Na dev PC

```bat
package.bat
```

→ vytvoří `certifikaty_deploy_20260415_a1b2c3d.zip`

Zkopíruj ZIP na flash disk.

### Na serveru

1. Zkopíruj ZIP do složky aplikace: `C:\inetpub\certifikaty\`

2. Spusť **CMD jako Administrator:**

   ```bat
   cd C:\inetpub\certifikaty
   update.bat CertifikátyPool certifikaty_deploy_20260415_a1b2c3d.zip evidence_cert
   ```

   | Parametr        | Popis                                     | Příklad               |
   |-----------------|-------------------------------------------|-----------------------|
   | 1. App Pool     | Název IIS Application Poolu               | `CertifikátyPool`     |
   | 2. ZIP soubor   | Název balíčku (nebo vynech — najde sám)   | `certifikaty_deploy_…zip` |
   | 3. NSSM služba  | Název Windows služby Waitress             | `evidence_cert`      |

   Název NSSM služby lze vynechat — výchozí hodnota je `evidence_cert`.
   Pokud NSSM služba na serveru neexistuje, skript to oznámí a pokračuje.

Skript provede:

| Krok | Co se stane                                                           |
|------|-----------------------------------------------------------------------|
| 1    | Zastaví IIS Application Pool (přestane přijímat požadavky)           |
| 2    | Zastaví Waitress službu přes NSSM (uvolní zámky na Python souborech) |
| 3    | Extrahuje ZIP přes stávající soubory (přepíše kód, zachová data)      |
| 4    | Nainstaluje nové/aktualizované Python závislosti                       |
| 5    | DB migrace — přidá nové tabulky, zachová existující data              |
| 6    | Spustí Waitress (NSSM) → čeká 3s → spustí IIS Application Pool       |

**Co se NIKDY nepřepíše:**

| Složka / soubor   | Obsah                         |
|-------------------|-------------------------------|
| `instance/`       | Databáze (všechna 4 prostředí)|
| `logs/`           | Logy aplikace                 |
| `uploads/`        | Nahrané soubory               |
| `.env`            | Konfigurace prostředí         |

### Ověření po aktualizaci

1. Otevři aplikaci v prohlížeči
2. Zkontroluj `VERSION.txt` ve složce aplikace
3. Zkontroluj logy: `logs\app.log`

---

## 8. Migrace existující instalace

Tato sekce je určena pro **server, kde aplikace již běžela** s prostředím TEST,
a nyní přecházíme na UAT + přidáváme SIT a PRELIVE.

### 8.1 Přejmenování databáze TEST → UAT

Pokud existuje stará databáze `instance\certifikaty_test.db`:

```bat
cd C:\inetpub\certifikaty
copy instance\certifikaty_test.db instance\certifikaty_uat.db
```

> `certifikaty_test.db` lze po ověření smazat, aplikace ji již nepoužívá.

### 8.2 Inicializace nových databází SIT a PRELIVE

Po nasazení nového balíčku (viz sekce 7) se nové databáze vytvoří automaticky
v kroku DB migrace (`update.bat` krok 4).

Pokud chceš inicializovat ručně (bez update):

```bat
cd C:\inetpub\certifikaty
venv\Scripts\python.exe -c "from app import create_app,db; app=create_app(); ctx=app.app_context(); ctx.push(); meta=db.metadatas.get('live') if hasattr(db,'metadatas') else db.metadata; [meta.create_all(bind=db.engines[e]) or print('OK: '+e) for e in ('live','uat','sit','prelive')]; ctx.pop()"
```

Po provedení by měly existovat tyto soubory:

```
instance\
  certifikaty.db            ← live (existující)
  certifikaty_uat.db        ← UAT (zkopírováno z test nebo nové)
  certifikaty_sit.db        ← SIT (nové, prázdné)
  certifikaty_prelive.db    ← PRELIVE (nové, prázdné)
```

### 8.3 Aktualizace .env

Zkontroluj hodnotu `REPORT_ENVS` v `.env`:

```env
# Zahrnout do reportu pouze produkci (doporučeno):
REPORT_ENVS=live

# Nebo více prostředí:
REPORT_ENVS=live,uat
```

Hodnota `test` již není platná — nahraď ji `uat`.

### 8.4 Restart aplikace po migraci

```bat
cd C:\inetpub\certifikaty
C:\Windows\System32\inetsrv\appcmd.exe stop apppool /apppool.name:"CertifikátyPool"
C:\Windows\System32\inetsrv\appcmd.exe start apppool /apppool.name:"CertifikátyPool"
```

---

## 9. Řešení problémů

### Aplikace nereaguje po update

Zkontroluj oba procesy — musí běžet oba:

```bat
REM 1. Stav NSSM / Waitress služby
nssm status evidence_cert

REM 2. Stav IIS Application Poolu
C:\Windows\System32\inetsrv\appcmd.exe list apppool CertifikátyPool
```

Ruční restart obou:

```bat
REM Restart Waitress
nssm stop evidence_cert
nssm start evidence_cert

REM Restart IIS pool (po startu Waitressu)
C:\Windows\System32\inetsrv\appcmd.exe stop apppool /apppool.name:"CertifikátyPool"
C:\Windows\System32\inetsrv\appcmd.exe start apppool /apppool.name:"CertifikátyPool"
```

### Chyba při spuštění aplikace

Spusť ručně a sleduj výstup přímo v konzoli:

```bat
cd C:\inetpub\certifikaty
venv\Scripts\python.exe wsgi.py
```

### Chybějící tabulky v databázi

```bat
cd C:\inetpub\certifikaty
venv\Scripts\python.exe -c "from app import create_app,db; app=create_app(); ctx=app.app_context(); ctx.push(); meta=db.metadatas.get('live') if hasattr(db,'metadatas') else db.metadata; [meta.create_all(bind=db.engines[e]) or print('OK: '+e) for e in ('live','uat','sit','prelive')]; ctx.pop()"
```

### NSSM služba nespustí aplikaci

```bat
REM Zkontroluj stav služby
nssm status evidence_cert

REM Zobraz logy NSSM
nssm dump evidence_cert

REM Restartuj službu
nssm restart evidence_cert
```

### Ověření, že Waitress naslouchá na portu 8080

```bat
netstat -ano | findstr :8080
```

### Logy aplikace

- Aplikační log: `logs\app.log` (rotace o půlnoci, archivace jako `logs\app.log.YYYY-MM-DD.zip`, drží se 90 dní)
- Logy služby: `logs\service.out.log` a `logs\service.err.log` (rotuje NSSM, viz sekce 5.5)

### Aplikační log se přestal zapisovat

Nejčastější příčina: půlnoční rotaci zablokoval jiný proces, který držel
`app.log` otevřený — typicky **druhá ručně spuštěná instance aplikace**
(`python wsgi.py` vedle běžící služby) nebo log otevřený v programu, který
soubor zamyká. Aplikace to nyní přežije (zaloguje selhání rotace do
`service.err.log` a pokračuje v zápisu), přesto platí:

- Nikdy nespouštěj druhou instanci aplikace nad stejnou složkou, dokud běží služba.
- Log prohlížej kopií nebo nástrojem, který soubor nezamyká (`type`, VS Code, `Get-Content -Tail`).
- Diagnóza: hledej `Rotace logu selhala` v `logs\service.err.log`.

### E-mail s reportem skončil v karanténě (phishing)

Hlavičky zprávy aplikace doplňuje správně (`Date`, `Message-ID`,
`Auto-Submitted`). Pokud Exchange/Defender přesto hlásí *„Phishing zjištěný
s vysokou pravděpodobností"*, je příčinou téměř vždy **selhání ověření
odesílatele (SPF/DKIM/DMARC)** — aplikační server posílá mail s adresou firemní
domény (`MAIL_SENDER_ADDRESS`), ale není uveden jako povolený odesílatel této
domény. To z pohledu filtru vypadá jako spoofing. Řešení domluv s správci pošty:

1. **SPF:** přidat IP aplikačního serveru (nebo interní relay) do SPF záznamu
   domény odesílatele, případně posílat přes relay, který už v SPF je.
2. **Exchange Online:** přidat výjimku — Tenant Allow List / mail flow rule
   pro adresu odesílatele + IP serveru (interní notifikační systém).
3. Ověřit, že `MAIL_SENDER_ADDRESS` je doména, za kterou smí SMTP server
   (`MAIL_SERVER`) odesílat — ne smyšlená adresa typu `noreply@example.com`.

Konkrétní důvod zamítnutí je vidět v karanténě v hlavičce zprávy
(`Authentication-Results: spf=fail / dmarc=fail` apod.).

### Stav databází — přehled souborů

```bat
dir C:\inetpub\certifikaty\instance\
```

Očekávaný výstup:
```
certifikaty.db
certifikaty_uat.db
certifikaty_sit.db
certifikaty_prelive.db
```

## 10. Přihlášení (Windows SSO) a role

Aplikace pozná uživatele podle Windows účtu, pod kterým je přihlášený na svém PC. Ověření dělá **IIS**
(Windows Authentication) a předá aplikaci jméno účtu v hlavičce `X-Remote-User`. Aplikace jen ověřuje, že hlavička
přišla z důvěryhodné adresy (`AUTH_TRUSTED_PROXIES`, výchozí `127.0.0.1`), a podle účtu přidělí **roli**.

| Role | Co smí |
|---|---|
| **Prohlížení** (`viewer`) | přehled, končící certifikáty, servery, historie, export |
| **Úpravy** (`editor`) | navíc přidávat a upravovat certifikáty a servery, import z Excelu |
| **Administrátor** (`admin`) | navíc mazat, nastavení (SMTP, prahy, reporty), odeslání reportu, správa uživatelů |

Nový uživatel se po prvním otevření aplikace objeví na stránce **Uživatelé** jako „Čeká na schválení“ a do té doby
nemá přístup. Admin mu tam přidělí roli. Každá změna v **Historii** nese jméno uživatele, který ji provedl.

### 10.1 Nastavení v `.env`

```
ADMIN_USERS=PMB\jnovak,PMB\ibadmin       # první administrátoři (stále admin, i kdyby jim někdo roli změnil)
LOCAL_ADMIN_USER=admin                    # záložní lokální admin pro případ nedostupnosti SSO
LOCAL_ADMIN_PASSWORD_HASH='...'           # hash hesla, bez něj je záložní účet vypnutý
SECRET_KEY=...                            # povinně nastavit (podepisuje přihlášení lokálního admina)
```

Hash hesla záložního admina:

```
venv\Scripts\python.exe -c "from werkzeug.security import generate_password_hash as g; print(g('NOVE-HESLO'))"
```

Výsledek vložte do `.env` do jednoduchých uvozovek. Záložní admin se přihlašuje na `/evidence_certifikatu/login`.

### 10.2 Nastavení IIS (na existující IIS aplikaci)

Aplikace běží jako služba `evidence_cert` (waitress, port 8080) a před ní už stojí IIS jako reverzní proxy
(IIS aplikace `evidence_certifikatu` se složkou aplikace a souborem `web.config`). Nic nového se nezakládá,
jen se na té aplikaci zapne Windows přihlášení a IIS začne posílat jméno uživatele.

1. **Windows Authentication musí být nainstalovaná** (jednou): Server Manager → Add Roles and Features → Web Server →
   Security → *Windows Authentication*, nebo `Install-WindowsFeature Web-Windows-Auth`.
2. **Ověření uživatele na IIS aplikaci:** IIS Manager → web → aplikace `evidence_certifikatu` → *Authentication*:
   *Anonymous Authentication* → **Disable**, *Windows Authentication* → **Enable**
   (v *Providers* nahoře *Negotiate*, pod ním *NTLM*).
3. **Povolit proměnnou** (jednou, název webu upravte; příkaz jako správce):
   ```
   %windir%\system32\inetsrv\appcmd.exe set config "NAZEV_WEBU" -section:system.webServer/rewrite/allowedServerVariables /+"[name='HTTP_X_REMOTE_USER']" /commit:apphost
   ```
4. **`web.config`:** ve složce IIS aplikace (je to složka aplikace, např. `D:\Others\app\iis_apps\check_cert_app`)
   nahradit soubor `web.config` verzí z tohoto repozitáře. Liší se jen tím, že do pravidel přibyl řádek
   `<set name="HTTP_X_REMOTE_USER" value="{LOGON_USER}" />`, který předá jméno uživatele aplikaci. `update.bat`
   tento soubor nepřepisuje, proto se kopíruje ručně (stačí jednou).
5. **`.env` a restart:** viz 10.1, plus `APP_URL=http://adresa-iis/evidence_certifikatu`; pak `nssm restart evidence_cert`.
6. **Prohlížeče:** aby se přihlášení stalo bez ptaní na heslo, musí být adresa v zóně *Místní intranet*
   (běžně řeší GPO, *Site to Zone Assignment List*). Jinak Edge/Chrome jednou požádají o doménové heslo.
7. **Volitelně:** zablokovat ve firewallu příchozí port 8080 ze sítě (jen localhost), aby šlo do aplikace jen přes IIS.
   Pozor, `update.bat` nastavuje službu na `--host=0.0.0.0`, spolehlivější je proto firewall.

> Tuto část jsem nemohl vyzkoušet na vašem serveru. Po nasazení ověřte, že se v pravém horním rohu aplikace zobrazí
> vaše jméno. Pokud ne, podívejte se, jestli IIS skutečně posílá hlavičku (`X-Remote-User`) a jestli aplikace
> vidí požadavky z adresy v `AUTH_TRUSTED_PROXIES` (výchozí `127.0.0.1`, IIS volá `localhost`).

### 10.3 Vývoj bez IIS

Na vývojovém PC (WSL) není SSO k dispozici. Do `.env` dejte buď záložního admina (`LOCAL_ADMIN_PASSWORD_HASH`),
nebo simulovaný účet jen pro localhost: `AUTH_DEV_USER=PMB\jnovak` a ten samý účet do `ADMIN_USERS`.
Na produkci `AUTH_DEV_USER` nenastavujte.

### 10.4 Nouzové vypnutí

`AUTH_ENABLED=false` v `.env` vypne přihlášení úplně (každý je admin). Používat jen dočasně a vědomě, např. při
chybném nastavení IIS. Při startu se do logu zapíše varování.

---

*Dokument aktualizován: 2026-06-10*
