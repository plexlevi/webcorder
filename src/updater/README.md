# WebCorder Update System

Az automatikus frissítési rendszer lehetővé teszi a felhasználók számára, hogy egyszerűen frissítsék a WebCorder alkalmazást anélkül, hogy manuálisan le kellene tölteniük az új verziókat.

## Jellemzők

- **Automatikus ellenőrzés**: A program minden indításkor ellenőrzi, hogy van-e új verzió
- **Elegáns UI**: Felugró ablak az új verziókról részletes információkkal
- **Felhasználói kontroll**: 
  - "Telepítés most" - Automatikus letöltés és telepítés
  - "Később" - Elhalasztás a következő indításra
  - "Ne kérdezd meg újra" - Adott verzió kihagyása
- **Csendes telepítés**: Automatikus telepítés háttérben
- **Biztonságos**: Csak aláírt kiadásokat telepít

## Konfiguráció

### GitHub Repository
Az update rendszer a GitHub Releases-t használja:
- Tulajdonos: `plexlevi`
- Repository: `webcorder`
- API endpoint: `https://api.github.com/repos/plexlevi/webcorder/releases/latest`

### Privát repository esetén
Ha a repository privát, szükséges GitHub token:
```python
# src/ui/app.py-ban
self.update_manager = UpdateManager(
    config_path(), 
    repo_owner="plexlevi", 
    repo_name="webcorder",
    github_token="YOUR_GITHUB_TOKEN_HERE"  # Personal Access Token
)
```

### Verzió konfiguráció
A jelenlegi verzió a `src/updater/version_manager.py`-ban található:
```python
self.current_version = "1.0"  # Frissíteni kell minden kiadásnál
```

## Használat

### Automatikus ellenőrzés
- Az alkalmazás indításkor automatikusan ellenőrzi az új verziókat
- 24 óránként maximum egyszer ellenőriz
- Ha új verzió van, felugró ablak jelenik meg

### Manuális ellenőrzés
- "🔄 Check Updates" gomb az Actions sorban
- Azonnali ellenőrzés, idő limitek figyelembevétele nélkül

### Felhasználói döntések
1. **Telepítés most**: 
   - Letölti az új verziót temp mappába
   - Elindítja a telepítőt csendes módban
   - Bezárja a jelenlegi alkalmazást
   
2. **Később**: 
   - Bezárja a dialógust
   - Következő indításkor újra kérdez
   
3. **Ne kérdezd meg újra**: 
   - Elrejti az adott verziót
   - A config fájlba menti a kihagyott verziót
   - Újabb verzió esetén újra kérdez

## Konfiguráció file struktúra

A `config/webcorder_data.json` fájlban:
```json
{
  "updates": {
    "skipped_versions": ["1.1", "1.2"],
    "last_check_time": 1694876543.123
  }
}
```

## Release követelmények

Ahhoz, hogy az automatikus frissítés működjön, a GitHub Release-nek tartalmaznia kell:
- Tag: `v1.X` formátumban (pl. `v1.1`)
- Asset: `WebCorder-Setup-v1.X.exe` telepítő fájl
- Release notes: Markdown formátumban az újdonságokról

## Hibaelhárítás

### Gyakori problémák
1. **404 hiba**: Repository nem létezik vagy privát, token hiányzik
2. **Hálózati hiba**: Internet kapcsolat probléma
3. **Letöltési hiba**: Nem megfelelő asset nevek vagy hiányzó fájlok
4. **Telepítési hiba**: Inno Setup telepítő problémák

### Debug információ
Az update rendszer naplózza a műveleteket az alkalmazás log ablakába:
- "Checking for updates..."
- "GitHub API error: 404"
- "Update available: v1.X"
- "Download started..."
- "Installation completed"

## Fejlesztői megjegyzések

### Biztonság
- SSL/TLS kapcsolat a GitHub API-hoz
- Csak aláírt GitHub Release-ek
- Temp fájlok automatikus törlése

### Teljesítmény
- Aszinkron letöltés aiohttp-vel
- Progress callback UI frissítéshez
- Háttér szálak a UI blokkolás elkerülésére

### Karbantartás
- Verzió szám frissítése minden kiadásnál
- GitHub token rotálás privát repo esetén
- Update rendszer tesztelése új verzió előtt
