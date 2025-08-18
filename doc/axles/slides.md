# Možnosti ML na osnih signalih

- Osnovni podatki so event-i $E$, ki med drugim [vsebujejo](s_p.png)
  
  - $s$ signal iz detektorjev osi (analogen signal)
  
  - $p$ pulzi (digitalen signal)
  - Dva spiska vozil 
    - `detected_vehicles`, ki jih producira modul `vehicle_fad`
    - `weighed_vehicles`, rezultat tehtanja in morebitne rekonstrukcije
    - V obeh imajo vozila spisek medosnih razdalj in pulzov
- Rezultat tehtanja so obdelani event-i in NSWD-ji

## Obdelava podatkov na Šentvidu

1. Neposredno tehtanje z rekonstrukcijo — `rp01`
2. Skripta `qa.py` — `rp02`
3. Strojni popravki `fix.py` — `rp02`
4. Ročni popravki s `SiWIM-D` — `rp03`
5. Skripta `label_braid_photos.py` za ročno označevanje — `metadata.hdf` 
   - Prave skupine osi, prebrane s slike
   - Potencialno dvignjene osi
- Koraka 2 in 3 se poznata samo v NSWD 
- Korak 4 se pozna tudi v event-ih, vendar so le-ti izgubljeni


## Rekonstrukcija pulzov za končne rezultate

- Pulzi v `detected` in `weighed`
  - Detektirani in, v `weighed`, potencialno rekonstruirani
  - Brez informacije o strojnih in ročnih popravkih
- Strojno in ročno popravljene medosne razdalje
- Iz tega je moč rekonstruirati osne pulze za `final`

## Izbira vozil (1)

Skripa `nn_vehicles.py`

- Vhodni podatki:
  - `braid.nswd` v `rp01` in `rp03`
  - `metadata.hdf5`
  - `recognized_vehicles.json`
- Samo vozila, ki so sama na prvem pasu in ki so v obeh NSWD-jih
  - razdeljevanje in združevanje vozil
  - napake pri označevanju

- Ostane 199820 vozil

## Izbira vozil (2)

- Izberemo samo tista, ki so v `metadata.hdf5`, skupaj 166551 vozil
- 125161 vozil ni bilo pregledanih
- 41390 preostalih vozil:
  - Pri 34087 se skupine osi na sliki in NSWDjih ujemajo
  - Pri 7303 pa ne:
    - 6141 dvignjeno os (nemogoče detektirati)
    - 1162 (2.8%) "pravo" neujemanje
  

Rezultat je `nn_vehicles.json` (vsebina je opisana v  [axles.pdf](axles.pdf)):

- Timestamp-e vozil in eventov
- Polja `photo_match`, `axle_groups` in `raised_axles` iz `metadata.hdf5`
- Za `weighed` in `final` podatke iz NSWD:
  - `axle_groups`, `axle_distance`
  - Zastavice ki opisujejo katere spremembe so se zgodile

## Reprocesiranje event-ov s SiWIM

- Diagnostike `vehicle_fad` delno izgubljeni, delno nikoli generirani
- Kombinacija dveh signalov (navzkrižna korelacija)
- Zaradi prihranka prostora in časa tako konstruiran signal ni bil shranjen
- Ponovno generiranje diagnostik za  detekcijo osi
- Nemogoče ponovno pretehtati vozila (vplivnica)

## Ekstrakcija signalov in osnih pulzov iz event-ov (1)

Skripta `nn_axles_and_signals.py` 

- Datoteka `nn_vehicles.json` iz prejšnjega koraka
- Originalni event-i iz `rp01` za branje `detected` in `weighed` osnih pulzov
- Reprocesirani event-i za branje osnih signalov

Rezultat `nn_axles.json` ima razširjene vnose iz `nn_vehicles.json`

- Celoten opis je v  [axles.pdf](axles.pdf)
- Vsebuje dodatno informacijo o:
  - `detected` vozilih (pred tehtanjem in rekonstrukcijo)
  - Spisek `axle_pulses` za `detected` in `weighed` vozila (vrednost v spisku je indeks vzorca)

## Ekstrakcija signalov in osnih pulzov iz event-ov (2)

`nn_signals.hdf5` vsebuje grupe, npr.,  [2014-03-27-12-02-17-246](2014-03-27-12-02-16-234.event) in znotraj grupe `numpy` array-je, ki predstavljajo signale

- `s111`: Prvi signal za detekcijo osi.
- `s112 a11`: Drugi signal za detekcijo osi.
- `11admp`: Kombinirani signal za detekcijo osi.
- `11admp''`: Signal z odšteto envelopo. 
- `11avg1`: Prvo drseče povprečje signala `11admp''` z dolžino povprečenja enako 0.3&nbsp;m.
- `11avg2`: Drugo drseče povprečje signala `11admp''` z dolžino povprečenja enako 1.1&nbsp;m.
- Razlika `11diff = 11avg1 - 11avg2`, ki je osnova za algoritem za detekcijo. 

## Generiranje pulzov za končno verzijo vozil

Za končna vozila nimamo osnih pulzov.

Skripta `nn_pulses.py` prebere  `nn_axles.json`, doda `axle_pulses` vnose za `final` vozila in rezultat prepiše v `nn_pulses.json`. Algoritem je:

- `diff.SequenceMatcher` poišče podobnosti med medosnimi razdaljami `weighed` in `final` vozili.
- Če se niti ena medosna razdalja ne ujema, vozilo ni kandidat za učenje in polje `eligible` se nastavi na `False`. Takšnih vozil je 161.
- Drugače poišče najdaljši ujemajoč se odsek. S pomočjo tega in osnih pulzov iz `weighed` izračuna faktor skaliranja med medosnimi razdaljami in ga shrani v polje `scale`.
- S to informacijo se generira nove osne pulze za `final`.

## Učenje

34087 vozil ima tako ali drugače pravilno detektirane osi, 1162 pa ne, oboje ročno preverjeno.

Podatki so v BrAId pCould v `10_podatki/Axles`.

- Signali iz detektorjev osi `nn_signals.hdf5`
  - Signal `11diff` in kasnejši algoritem zahtevata ročno nastavljanje parametrov
  - Morda kar `11admp` ali `11admp''`

- Osni pulzi `nn_pulses.json`

Preverjanje popravkov 1162 napačno detektiranih skupin osi kot kriterij za uspešnost učenja.

- V metapodatkih ni medosnih razdalj.
- Treba je primerjati ročno prebrane in generirane osne skupine
- To je možno s preprostim računom (opisanim v [axles.pdf](axles.pdf) )

Vsi dokumenti in skripte so na voljo na https://github.com/JanKalin/BrAId
