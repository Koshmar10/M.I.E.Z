# Fișa de direcție — atelierul 1

> **Inginerie Software 2026–27** · temă opțională, nu se notează.
> Atelierul 1 (S5, 26–30 oct) confirmă direcția în care vă duceți proiectul. Echipele care vin cu fișa au o discuție mai scurtă și mai precisă.
>
> **Cum:** copiați fișierul în rădăcina repo-ului ca `DIRECTIE.md`, completați-l și faceți commit înainte de slotul vostru de atelier. Veniți la atelier cu el în repo.
> **Atelierul:** vom posta un calendar; fiecare echipă își rezervă slotul în intervalul de 4 ore, cu Rareș și Petru.
> **Lungime:** cel mult două pagini. Puncte scurte, nu eseuri.
> **Când:** secțiunile 1–6 după cursul 2 (S3); secțiunile 7–8 după cursul 3 (S4).
> **AI:** permis și declarat (în mesajul de commit), ca la orice livrabil. La atelier, fiecare membru trebuie să poată explica orice rând de aici.
>
> Indicațiile sunt comentarii `<!-- ... -->`: nu apar pe GitHub, le puteți lăsa sau șterge.

| | |
|---|---|
| **Echipa** | M.I.E.Z. |
| **Membri** | Neacsa Denis, Draghiceanu Petru, Zaharia Aris, Olteanu Andrei, Sava Darius |
| **Repo** | https://github.com/Koshmar10/M.I.E.Z |

---

## 1. Sistemul, așa cum e acum (as-is)

<!-- Ce face, în 3 propoziții. Pentru cine.
     Starea reală: ce merge, ce e pe jumătate, ce nu merge deloc.
     Cum ați aflat: ce ați citit și ce ați rulat (README, issues, teste, cod). -->

- **M.I.E.Z** este o platformă web all-in-one de management business pentru IMM-uri, cu module de HR, Sales, Inventory și IT Support, dashboard-uri role-aware și un asistent AI conversațional. Construită pe Django 5.2 + React/TypeScript, deployată cu Docker Compose pe AWS EC2.
- **Ce merge:** CRUD complet pe angajați, comenzi, stocuri, tickete IT; dashboard-uri cu KPI-uri per modul; workflow engine cu trimitere email SMTP; asistent AI cu tool-use scoped pe rol (Claude); rapoarte generate AI; notificări; sistem de contracte cu status automat; payroll per lună.
- **Ce nu merge / lipsește:** aplicația nu suportă mai multe firme (single-tenant, modelul `User` nu are FK la o entitate `Company`); modulele sunt izolate între ele (o comandă de vânzare nu scade stocul, un angajat nou nu apare automat în IT); nu există flow de onboarding; acțiunea „Post to Channel" din workflow engine e stub (nu trimite real pe Discord/Slack); nu există integrări cu mediul business românesc (salariu net, concedii, CUI, e-factura, curs BNR); nu se generează documente PDF; nu există import Excel pentru stoc; agentul AI nu are guardrails robuste și nu poate răspunde din documente încărcate.
- **Cum am aflat:** README.md, CLAUDE.md, analiza modelelor (`api/models/user.py` — fără FK la Company), cod frontend (module izolate per sidebar), workflow engine (acțiuni stub), seed_db.

## 2. Direcția (to-be)

<!-- Cel mult trei obiective pentru semestrul acesta: ce întăriți, ce reparați, ce schimbați.
     Pentru fiecare: de ce acum și cum veți ști că l-ați atins. -->

| # | Obiectiv | De ce acum | Cum știm că l-am atins |
|---|---|---|---|
| O1 | **Multi-tenancy & integrare cross-modul** — model de Firmă, model comun de angajat cu drepturi, integrare Sales↔Inventory, Angajat↔IT, Angajat↔HR | Fără firmă, aplicația nu e utilizabilă real; fără integrare, modulele sunt 4 aplicații separate | Există model `Company`; userul aparține unei firme; o comandă scade stocul; un angajat nou apare în IT și HR |
| O2 | **Flow de onboarding + Integrări business RO** — onboarding complet, salariu net automat, zile concediu calculate, client cu CUI, curs BNR EUR→RON, generare e-factura | Diferențiatorul pe piața RO; onboarding-ul conectează toate modulele | Onboarding creează contract + cont + asset IT + pontaj; salariu net corect cu CAS/CASS/impozit; e-factura XML validă |
| O3 | **Guardrails agent + funcționalitate extinsă** — agent robust, răspunde din regulament intern, generare PDF, import Excel stoc, webhook Discord/Slack real, serviciu Docker date demo | Impact vizual mare la demo; guardrails = calitate producție | Agentul refuză acțiuni în afara scopului; răspunde din documente; PDF-uri descărcabile; Excel importat; mesaje pe Discord |

**Ce nu facem:**

- Nu construim un portal complet de clienți (Customer Portal) — doar explorăm fezabilitatea
- Nu construim modul de contabilitate completă (plan de conturi, balanță, bilanț)
- Nu facem integrare cu ANAF SPV sau RO e-Transport
- Nu implementăm multi-currency complet (doar curs EUR→RON de la BNR)

## 3. Stakeholderii

<!-- Nu doar utilizatorii (personas de la MDS): oricine e afectat de sistem. -->

| Cine | Ce vrea de la sistem | Cum aflăm ce vrea (interviu, observație, scenariu, repo) |
|---|---|---|
| **CEO / Administrator firmă** | Vedere consolidată cross-modul, rapoarte agregate, decizii rapide pe baza AI | Scenarii demo, feedback atelier |
| **Manager HR** | Onboarding rapid, calcul salariu net corect, concedii automate, regulament intern accesibil prin AI | Legislația muncii RO (Codul Muncii), interviuri cu procese HR reale |
| **Manager Vânzări** | Integrare stoc-comenzi, clienți cu CUI valid, facturi e-factura | Cerințele ANAF e-factura, fluxul real de vânzare B2B |
| **Angajat obișnuit** | Pontaj din portal, cereri concediu self-service, consultare regulament intern prin AI | Observație UX, feedback utilizatori |
| **Coordonator proiect (profesor)** | Demo funcțional, fișa de direcție completă, cod documentat, arhitectură coerentă | Cerințele cursului, atelier |

## 4. Resursele noastre

<!-- Realist, nu optimist. O tehnologie pe care nu o știe nimeni din echipă primește automat risc 9 (secțiunea 6). -->

| Resursă | Ce avem, realist | Ce ne lipsește |
|---|---|---|
| **Oameni** <br><sub>membri, ore pe săptămână fiecare, cine lipsește când</sub> | 5 membri | *(de completat)* |
| **Cunoștințe** <br><sub>ce stăpânim, ce ar fi prima dată</sub> | Django + DRF, React + TS, Docker, REST APIs, Claude AI tool-use | Multi-tenancy la scară, legislație fiscală RO (CAS/CASS/impozit), standard e-factura UBL 2.1, API BNR |
| **Tehnice** <br><sub>stack, medii, CI, hosting, servicii externe</sub> | Python 3.13, Django 5.2, React + Vite, PostgreSQL, Docker Compose, GitHub Actions CI/CD, Claude API | Webhook Discord/Slack, librărie PDF, parser Excel |
| **Financiare** <br><sub>buget </sub> | 0 RON | Finante |
| **Acces la AI** <br><sub>modele, planuri, cine le are, limite; ce date nu avem voie să punem în model</sub> | Anthropic Claude (deja integrat pentru asistent și rapoarte); acces la modele prin credite studenți | Limite de rate pe planul curent; nu punem date personale reale în model |

## 5. Fezabilitate

<!-- După Sommerville, Software Engineering, ed. 10, p. 104, adaptat.
     Un „nu" sau „nu știm" e un subiect bun pentru atelier. -->

| Întrebare | Da / Nu / Nu știm | De ce |
|---|---|---|
| Contribuie direcția la ce vor stakeholderii de la secțiunea 3? | **Da** | Onboarding, integrări RO și agent îmbunătățit acoperă nevoile tuturor stakeholderilor identificați |
| Se poate face până la final de semestru, cu resursele de la secțiunea 4? | **Da** | Obiectivele sunt incrementale; fiecare feature se poate livra independent; stack-ul e deja matur |
| Se integrează cu ce există deja în sistem și în jurul lui? | **Da** | Modelul Company se adaugă peste User existent; integrările cross-modul folosesc signals Django; PDF/Excel sunt librării Python standard |

## 6. Primele cinci riscuri

<!-- Tip: estimation / organizational / people / requirements / technology / tools.
     Impact și probabilitate de la 1 la 3; scor = impact × probabilitate (1–2 mic, 3–4 mediu, 6–9 mare).
     Strategie: avoid / minimize / contingency. -->

| # | Risc | Tip | Impact | Prob. | Scor | Strategie |
|---|---|---|---|---|---|---|
| R1 | Multi-tenancy necesită migrare de date și modificarea tuturor query-urilor existente | technology | 3 | 2 | 6 | **minimize** — adăugăm `company` FK incremental, cu migrare backwards-compatible |
| R2 | Calculul salariului net greșit (legislație fiscală RO complexă, se schimbă anual) | requirements | 3 | 2 | 6 | **minimize** — folosim formulele oficiale 2024–2025, cu disclaimer „nu înlocuiește un contabil" |
| R3 | Generarea e-factura nu respectă standardul UBL 2.1 complet | technology | 2 | 3 | 6 | **minimize** — generăm XML minimal valid, testat cu validatorul ANAF public |
| R4 | Echipa nu are experiență cu toate tehnologiile noi (WeasyPrint, openpyxl, Discord webhooks) | people | 2 | 2 | 4 | **minimize** — PoC rapid în primele 2 săptămâni; tutoriale abundente, librării mature |
| R5 | Scope creep din lista mare de features propuse | estimation | 2 | 3 | 6 | **avoid** — prioritizare strictă must/should/could; „ce nu facem" explicit definit |

## 7. Cerințele candidate (după S4)

<!-- Între 5 și 10. Cerințele stau în repo, lângă cod și lângă testele care le verifică (cursul 3).
     Prioritate: must / should / could / won't (won't = nu de data asta).
     Tip: funcțională (F) sau nefuncțională: product / organizational / external (Sommerville, Fig. 4.3).
     Sursa: stakeholderul, issue-ul, codul sau testul din care vine, și cine a confirmat-o (o cerință extrasă din cod nu e confirmată de cod).
     De ce: rationale, ca să știți pe cine întrebați când se schimbă.
     Cum verificăm: un test, sau o măsură cu prag. „Să fie rapid" nu e cerință; „harta se încarcă în sub 2 s pentru 95% din cereri" este. -->

| # | Cerința | Prioritate | Tip | Sursa · confirmată de | De ce (rationale) | Cum verificăm |
|---|---|---|---|---|---|---|
| C1 | Aplicația suportă mai multe firme (model `Company`, user aparține unei firme, datele izolate per firmă) | **must** | F | Analiză cod (`User` fără FK la Company) · echipă | Fără multi-tenancy nu se poate demonstra un scenariu real cu mai multe firme | Test: 2 firme create, user din firma A nu vede datele firmei B |
| C2 | Modulele comunică între ele: o comandă de vânzare scade stocul automat, un angajat nou primește asset IT, HR vede angajatul | **must** | F | Analiză cod (module izolate) · echipă | Fără integrare, aplicația e 4 aplicații separate, nu un sistem unitar | Test: creare comandă → `StockMovement` outbound apare automat |
| C3 | Flow complet de onboarding: creare angajat → contract → cont user → asset IT → pontaj inițial | **must** | F | Cerință echipă · stakeholder HR | Onboarding-ul e procesul care conectează toate modulele și demonstrează integrarea | Test E2E: un angajat nou trece prin toți pașii automat |
| C4 | Salariu net calculat automat (CAS 25%, CASS 10%, impozit 10% pe venitul net) | **should** | F | Cerință echipă · legislația muncii RO | Diferențiator pe piața RO; elimină calcul manual eronat | Test: salariu brut 5000 RON → net ≈ 2750 RON |
| C5 | Zile de concediu calculate automat (21 zile/an standard, pro-rata la angajare) | **should** | F | Cerință echipă · Codul Muncii art. 145 | Automatizează un calcul manual frecvent, reduce erori | Test: angajat din 1 iulie → 10.5 zile disponibile |
| C6 | Adăugare client cu CUI (validare format, preluare date de la ANAF/openapi.ro) | **should** | F | Cerință echipă · flux B2B real | Orice firmă din RO identifică clienții prin CUI | Test: CUI valid → denumire și adresă populate automat |
| C7 | Curs valutar BNR EUR→RON live + generare e-factura XML (UBL 2.1 minimal) | **could** | F | Cerință echipă · obligație legală e-factura din 2024 | Integrare cu ecosistemul fiscal RO | Test: XML generat trece validatorul ANAF |
| C8 | Workflow „Post to Channel" trimite real pe Discord/Slack via webhook | **must** | F | Analiză cod (acțiune stub) · echipă | E gratuit, se face în câteva ore, arată excelent la demo | Test: workflow se execută → mesaj vizibil pe canalul Discord |
| C9 | Agent cu guardrails (refuză acțiuni neautorizate), răspunde din regulamentul intern (documente încărcate), generare PDF rapoarte, import Excel stoc | **should** | F + nefuncțional (product) | Cerință echipă · stakeholder angajat | Calitate producție + funcționalitate demo-ready | Test: agent refuză cerere în afara rolului; PDF valid generat; Excel importat corect |
| C10 | Serviciu Docker de generare date demo + portal pontaj angajat (self-service) | **could** | F | Cerință echipă · nevoie demo | Date realiste pentru demo; pontajul e self-service pentru angajat | Test: `docker compose up` generează date; angajatul își vede și completează pontajul |

## 8. Primele trei architecture characteristics (dacă ajungeți până aici)

<!-- Doar trei: cele fără de care sistemul nu reușește (Richards & Ford, cap. 4–5; vezi Vasa).
     Fiecare cu cerința (C1…) sau domain concern-ul din care vine. Cele implicite contează: nu le scrie nimeni, dar le știți din domeniu
     (de exemplu, toată lumea se înscrie în ultimele 10 minute). -->

| # | Architecture characteristic | Din ce cerință sau domain concern vine | Explicită / implicită |
|---|---|---|---|
| A1 | **Data isolation** | C1 — mai multe firme cu date complet izolate; un utilizator nu trebuie să vadă niciodată datele altei firme | Explicită |
| A2 | **Modularity / Integrability** | C2, C3 — modulele trebuie să comunice prin interfețe clare (signals, services); onboarding-ul traversează HR→IT→Contracts | Explicită |
| A3 | **Security / Authorization** | C1 (izolare date per firmă), C9 (guardrails agent), roluri existente — fiecare layer (UI, API, agent) trebuie să respecte permisiunile | Implicită — deja role-based, dar multi-tenancy adaugă un al doilea axis de izolare |

## 9. Întrebări pentru atelier

<!-- Ce nu ați putut decide singuri. -->