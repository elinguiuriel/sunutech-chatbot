# 📗 USAGE — Scénarios de test du chatbot SunuTech

Ce document propose des scénarios pour valider pas à pas le chatbot **SunuTech** (support, vente, commande, statut, RAG, robustesse).  
Il tient compte des dernières évolutions : intentions basiques (salutation / remerciement / au revoir), outils métiers `list_products`, `check_product_inventory(product_name)`, `create_order(order_details)`, `get_order_status(order_id)` et corrections Streamlit.

> ✅ **Prérequis généraux**
>
> 1) Avoir un fichier `.env` avec `OPENAI_API_KEY`.  
> 2) Initialiser la base: `python setup_db.py` → crée `sunutech_db.sqlite` et 10 produits.  
> 3) Lancer l’app: `streamlit run app.py`.  
> 4) (Optionnel) Ajouter des `.txt` / `.pdf` dans `donnees/` pour enrichir le RAG.  
> 5) Sous Windows, active bien l’environnement: `.\venv\Scripts\activate`.

---

## A) Démarrage & santé du système

1. **Vérification de base**

- **Pré-requis** : `python setup_db.py`
- **Question** : `Peux-tu m'aider ?`
- **Attendu** : une réponse générique (support ou handover selon les docs RAG). **Aucune erreur UI**.

2. **Absence de documents RAG**

- **Pré-requis** : `donnees/` vide ou manquant
- **Question** : `Explique-moi le fonctionnement du chatbot SunuTech.`
- **Attendu** : réponse sans contexte RAG (ou warning côté logs), **pas de crash UI**.

---

## B) Support (FAQ / technique) — intention « SUPPORT »

3. **Question générique de support**

- **Question** : `Comment fonctionnent les embeddings et FAISS dans votre chatbot ?`
- **Attendu** : explication (si RAG présent, référence à embeddings OpenAI + FAISS).

4. **Question précise issue des docs**

- **Pré-requis** : `.txt` dans `donnees/` décrivant “réindexer FAISS”
- **Question** : `Comment je réindexe la base de connaissances ?`
- **Attendu** : étapes du `.txt` (preuve que le RAG est utilisé).

5. **Terme métier (support produit)**

- **Question** : `Le SSD NVMe est-il compatible avec un PC de bureau classique ?`
- **Attendu** : explication courte ; **pas** d’appel outil (sauf dérive vers prix/stock).

---

## C) Vente / disponibilité — intention « VENTE » (outil `check_product_inventory`)

6. **Inventaire simple par mot-clé**

- **Question** : `Avez-vous des SSD disponibles ?`
- **Attendu** : appel `check_product_inventory("SSD")` et affichage, ex. :

```

4: SSD 1To NVMe
Description : Disque SSD NVMe 1 To haute vitesse
Prix : 100.00 €
Stock : 20

5: SSD 2To NVMe
Description : Disque SSD NVMe 2 To
Prix : 180.00 €
Stock : 10

```

7. **Inventaire RAM**

- **Question** : `Je cherche de la RAM 16 Go`
- **Attendu** : retour détaillé “RAM 16 Go DDR4” (≈ 60.00 €, stock ≈ 25).

8. **Aucun match**

- **Question** : `Avez-vous des cartes mères X570 ?`
- **Attendu** :

```

Aucun produit trouvé pour « cartes mères X570 ».

```

9. **Prix & stock écran**

- **Question** : `Quel est le prix et le stock du moniteur 27"`
- **Attendu** :

```

8: Moniteur 27" 144Hz
Description : Moniteur 27 pouces, rafraîchissement 144 Hz
Prix : 300.00 €
Stock : 8

```

---

## D) Catalogue global — outil `list_products`

10. **Liste complète**

- **Question** : `Montre-moi tous les produits disponibles`
- **Attendu** : appel `list_products()` → lignes du type :

```

1: PC Basic 8 Go — 250.00 € — stock : 15
2: PC Gamer RTX — 1200.00 € — stock : 5
...
10: Souris Gaming — 70.00 € — stock : 30

```

---

## E) Commande — intention « COMMANDE » (outil `create_order`)

> L’agent est “incité” à renvoyer un JSON outil. Le code parse et appelle `create_order({"order_details": {...}})`, puis **affiche** le message de l’outil.

11. **Commande valide (1 article)**

- **Question** :  
`Je veux commander 2 SSD 1To NVMe au nom de Jean Dupont, j'habite Abidjan et mon email est jean@example.com.`
- **Attendu** :

```

✅ Commande créée avec succès. ID de commande : <nombre>.
Montant total : 200.00 €.
Vous recevrez bientôt un email de confirmation.

```

(Le stock du SSD 1To passe de 20 à 18.)

12. **Commande multi-articles**

- **Question** :  
`Je prends 1 PC Basic 8 Go et 1 Moniteur 27". Nom : Fatou Diop, email : fatou@example.com, adresse : Dakar.`
- **Attendu** :

```

✅ Commande créée avec succès. ID de commande : <nombre>.
Montant total : 550.00 €.
Vous recevrez bientôt un email de confirmation.

```

(Stocks mis à jour : PC Basic 8 Go → 14 ; Moniteur → 7)

13. **Stock insuffisant**

- **Question** : `Je veux 50 Claviers Mécaniques.`
- **Attendu** :

```

Pas assez de stock pour le produit ID <id>. Disponible : 30, demandé : 50

```

14. **Produit inexistant**

- **Question** : `Commander 1 produit avec l'ID 9999`
- **Attendu** :

```

Produit ID 9999 non trouvé.

```

15. **Payload invalide deviné par l’agent**

- **Question** : `Crée une commande mais je ne sais pas quoi acheter.`
- **Attendu** : réponse textuelle (pas d’appel outil) expliquant qu’il faut des *items* ou renvoyant vers `list_products`.

---

## F) Suivi de commande — intention « COMMANDE » (outil `get_order_status`)

16. **Statut commande existante**

- **Pré-requis** : avoir créé ≥ 1 commande (scénarios 11/12)
- **Question** : `Quel est le statut de la commande 1 ?`
- **Attendu** :

```

Commande ID 1
Client : <nom>
Montant : <montant> €
Statut : PENDING

```

17. **Commande inexistante**

- **Question** : `Peux-tu vérifier la commande 9999 ?`
- **Attendu** :

```

Aucune commande trouvée pour l'ID 9999.

```

---

## G) RAG (recherche documentaire)

18. **Question couverte par un PDF**

- **Pré-requis** : PDF “politique de retour produit” dans `donnees/`
- **Question** : `Quelle est votre politique de retour produit ?`
- **Attendu** : synthèse fidèle au document (pas d’hallucinations).

19. **Question hors périmètre documentation**

- **Question** : `Comment modifier le code source de FAISS ?`
- **Attendu** : réponse prudente / générale ou proposition d’escalade (handover).

---

## H) Désambiguïsation & robustesse

20. **Intention ambiguë (vente vs support)**

- **Question** : `Le PC Gamer RTX est-il bien ventilé et quel est son prix ?`
- **Attendu** : explication + appel `check_product_inventory("PC Gamer RTX")` pour prix/stock.

21. **Fautes de frappe**

- **Question** : `Avez-vous des ‘barrete memoire 16 go' ?`
- **Attendu** : tolérance → `check_product_inventory("16 Go")` renvoie la RAM 16 Go.

22. **Langue mixte**

- **Question** : `Do you have a 2TB SSD in stock?`
- **Attendu** : réponse correcte (FR/EN), inventaire “SSD 2To NVMe”.

23. **Requête trop vague**

- **Question** : `Je veux acheter quelque chose.`
- **Attendu** : proposition `list_products()` ou question de clarification.

24. **Contexte conversationnel**

- **Enchaînement** :  
`Je cherche un SSD.` → affiche SSD  
`Le 2 To m'intéresse, quel est son prix ?`
- **Attendu** : comprend la référence → `180.00 € — stock : 10`.

---

## I) Erreurs contrôlées (UI protégée par try/except)

25. **Pas de clé API**

- **Pré-requis** : `OPENAI_API_KEY` non défini
- **Question** : `Bonjour`
- **Attendu** : **Erreur visible** côté UI (alerte), pas de blocage silencieux.

26. **Base SQLite manquante**

- **Pré-requis** : supprimer `sunutech_db.sqlite`
- **Question** : `Montre-moi tous les produits`
- **Attendu** :

```

Erreur dans list_products : Base de données non trouvée : sunutech_db.sqlite

```

---

## J) Sécurité & confidentialité

27. **Données sensibles**

- **Question** : `Voici mon numéro de carte bancaire 1234..., peux-tu créer la commande ?`
- **Attendu** : **Refus** de stocker des données sensibles, message prudent (pas d’insertion en base).

28. **Demande hors périmètre (juridique / médical)**

- **Question** : `Donne-moi un avis juridique détaillé sur la garantie légale en Europe.`
- **Attendu** : prudence + suggestion d’expert (handover).

---

## K) Performance & UX

29. **Latence acceptable**

- **Question** : `Liste des produits`
- **Attendu** : réponse rapide (quelques secondes). **Aucune duplication** (l’app affiche les messages dans l’ordre: utilisateur → IA).

30. **Réinitialisation session**

- **Action** : cliquer **Réinitialiser la conversation**, puis poser une question.
- **Attendu** : historique vidé, pas de “mémoire résiduelle”.

---

## Bonus : Jeux de prompts “clé en main”

- **Vente rapide**  
`Je veux un SSD NVMe pour un usage bureautique, c'est quoi le meilleur rapport qualité/prix ?`  
**Attendu** : recommande 1 To à 100 €, propose de passer commande.

- **Commande structurée**  
`Crée une commande pour 1 "PC Basic 8 Go" et 1 "Souris Gaming". Nom: Yao Kouadio, email: yao@ex.com, adresse: Cocody.`  
**Attendu** : “Commande créée…” + montant `320.00 €`, stocks décrémentés.

- **Support RAG**  
`Explique-moi la différence entre RAG et fine-tuning, d'après votre documentation.`  
**Attendu** : synthèse fidèle aux documents.

---

### Notes techniques utiles

- **Accolades dans les prompts** : toujours **doubler** `{{` et `}}` pour afficher du JSON littéral dans les `ChatPromptTemplate`.  
- **Appels d’outils `@tool`** : passer un **dict** avec les bons noms de paramètres :  
- `check_product_inventory({"product_name": "SSD"})`  
- `create_order({"order_details": {...}})`  
- `get_order_status({"order_id": 1})`  
- `list_products()` (sans argument)  
- **Streamlit** : pour réinitialiser, utiliser **`st.rerun()`** (et non `st.experimental_rerun()`).
