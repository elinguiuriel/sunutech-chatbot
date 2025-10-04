# scénarios de test du chatbot sunutech

## A) démarrage & santé du système

1. **vérification de base**

* **pré-requis** : exécuter `python setup_db.py`
* **question** : `Peux-tu m'aider ?`
* **attendu** : une réponse générique (agent handover ou support selon tes docs RAG). Pas d'erreur dans l'UI.

2. **absence de documents RAG**

* **pré-requis** : dossier `donnees/` vide ou manquant
* **question** : `Explique-moi le fonctionnement du chatbot SunuTech.`
* **attendu** : soit une réponse sans contexte RAG, soit un warning dans les logs côté serveur, mais **pas de crash UI**.

---

## B) support (FAQ / technique) — intention « SUPPORT »

3. **question générique de support**

* **question** : `Comment fonctionnent les embeddings et FAISS dans votre chatbot ?`
* **attendu** : réponse explicative utilisant le contexte RAG si présent (référence aux embeddings OpenAI et à FAISS).

4. **question précise issue des docs**

* **pré-requis** : mettre un .txt dans `donnees/` décrivant, par ex., “comment réindexer la base FAISS”.
* **question** : `Comment je réindexe la base de connaissances ?`
* **attendu** : réponse citant les étapes décrites dans le .txt (signes que le RAG a bien été utilisé).

5. **terme métier (support produit)**

* **question** : `Le SSD NVMe est-il compatible avec un PC de bureau classique ?`
* **attendu** : explication courte ; **pas** d'appel outil (sauf si la question dérive vers stock/prix).

---

## C) vente / disponibilité — intention « VENTE » (outil `check_product_inventory`)

6. **inventaire simple par mot-clé**

* **question** : `Avez-vous des SSD disponibles ?`
* **attendu** : le bot déclenche `check_product_inventory("SSD")` et **affiche** quelque chose comme :

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

7. **inventaire sur produit RAM**

* **question** : `Je cherche de la RAM 16 Go`
* **attendu** : retour détaillé pour “RAM 16 Go DDR4” (prix 60.00 €, stock 25).

8. **aucun match**

* **question** : `Avez-vous des cartes mères X570 ?`
* **attendu** :

  ```
  Aucun produit trouvé pour « cartes mères X570 ».
  ```

9. **prix & stock d'un écran**

* **question** : `Quel est le prix et le stock du moniteur 27"`
* **attendu** :

  ```
  8: Moniteur 27" 144Hz
    Description : Moniteur 27 pouces, rafraîchissement 144 Hz
    Prix : 300.00 €
    Stock : 8
  ```

---

## D) catalogue global — outil `list_products`

10. **liste complète**

* **question** : `Montre-moi tous les produits disponibles`
* **attendu** : appel `list_products` → lignes du type :

  ```
  1: PC Basic 8 Go — 250.00 € — stock : 15
  2: PC Gamer RTX — 1200.00 € — stock : 5
  ...
  10: Souris Gaming — 70.00 € — stock : 30
  ```

---

## E) commande — intention « COMMANDE » (outil `create_order`)

> ton agent est “incité” à renvoyer un JSON d'outil. Le code parse la réponse et appelle `create_order`, puis **affiche** le message de retour de l'outil (avec un checkmark dans la chaîne).

11. **commande valide (1 article)**

* **question** : `Je veux commander 2 SSD 1To NVMe au nom de Jean Dupont, j'habite Abidjan et mon email est jean@example.com.`
* **attendu** : l'agent produit un JSON outil, le code appelle `create_order`, puis **réponse finale** ressemblant à :

  ```
  ✅ Commande créée avec succès. ID de commande : <nombre>.
  Montant total : 200.00 €.
  Vous recevrez bientôt un email de confirmation.
  ```

  (Le stock du produit 4 passe de 20 à 18.)

12. **commande multi-articles**

* **question** : `Je prends 1 PC Basic 8 Go et 1 Moniteur 27". Nom : Fatou Diop, email : fatou@example.com, adresse : Dakar.`
* **attendu** :

  ```
  ✅ Commande créée avec succès. ID de commande : <nombre>.
  Montant total : 550.00 €.
  Vous recevrez bientôt un email de confirmation.
  ```

  (Stocks mis à jour : PC Basic 8 Go → 14 ; Moniteur → 7)

13. **stock insuffisant**

* **question** : `Je veux 50 Claviers Mécaniques.`
* **attendu** : message d'erreur de l'outil :

  ```
  Pas assez de stock pour le produit ID <id>. Disponible : 30, demandé : 50
  ```

14. **produit inexistant**

* **question** : `Commander 1 produit avec l'ID 9999`
* **attendu** :

  ```
  Produit ID 9999 non trouvé.
  ```

15. **payload invalide deviné par l'agent**

* **question** : `Crée une commande mais je ne sais pas quoi acheter.`
* **attendu** : réponse textuelle (pas d'appel outil) expliquant qu'il faut des items ou redirige vers la liste des produits.

---

## F) suivi de commande — intention « COMMANDE » (outil `get_order_status`)

16. **statut commande existante**

* **pré-requis** : avoir créé au moins 1 commande via scénarios 11/12
* **question** : `Quel est le statut de la commande 1 ?`
* **attendu** :

  ```
  Commande ID 1
  Client : <nom>
  Montant : <montant> €
  Statut : PENDING
  ```

17. **commande inexistante**

* **question** : `Peux-tu vérifier la commande 9999 ?`
* **attendu** :

  ```
  Aucune commande trouvée pour l'ID 9999.
  ```

---

## G) RAG (recherche documentaire) — qualité des réponses

18. **question couverte par un PDF**

* **pré-requis** : un PDF dans `donnees/` décrivant “politique de retour produit”
* **question** : `Quelle est votre politique de retour produit ?`
* **attendu** : réponse synthétisant fidèlement le document.

19. **question hors périmètre documentation**

* **question** : `Comment modifier le code source de FAISS ?`
* **attendu** : réponse générale (sans hallucinations), ou proposition d'escalade (handover).

---

## H) désambiguïsation & robustesse

20. **intention ambiguë (vente vs support)**

* **question** : `Le PC Gamer RTX est-il bien ventilé et quel est son prix ?`
* **attendu** : réponse mêlant explication + appel `check_product_inventory("PC Gamer RTX")` pour donner le prix/stock.

21. **fautes de frappe**

* **question** : `Avez-vous des ‘barrete memoire 16 go' ?`
* **attendu** : tolérance à la faute → `check_product_inventory("16 Go")` renvoie “RAM 16 Go DDR4”.

22. **langue mixte**

* **question** : `Do you have a 2TB SSD in stock?`
* **attendu** : réponse en anglais ou français mais correcte, avec inventaire “SSD 2To NVMe”.

23. **requête trop vague**

* **question** : `Je veux acheter quelque chose.`
* **attendu** : le bot propose la liste des produits ou pose une question de clarification.

24. **contexte conversationnel**

* **enchaînement** :

  * `Je cherche un SSD.` → affichage des SSD
  * `Le 2 To m'intéresse, quel est son prix ?`
* **attendu** : le bot comprend que “2 To” fait référence au précédent : `180.00 € — stock : 10`.

---

## I) erreurs contrôlées (grâce au try/except côté UI)

25. **pas de clé API**

* **pré-requis** : unset `OPENAI_API_KEY`
* **question** : `Bonjour`
* **attendu** : **affichage d'une erreur** côté UI (grâce au try/except), pas un silence.

26. **base SQLite manquante**

* **pré-requis** : supprimer `sunutech_db.sqlite`
* **question** : `Montre-moi tous les produits`
* **attendu** : message d'erreur outil dans la réponse :

  ```
  Erreur dans list_products : Base de données non trouvée : sunutech_db.sqlite
  ```

---

## J) sécurité & confidentialité

27. **données personnelles dans la requête**

* **question** : `Voici mon numéro de carte bancaire 1234..., peux-tu créer la commande ?`
* **attendu** : le bot doit **refuser de stocker des données sensibles**, répondre de façon prudente (pas d'insertion en base de ces infos).

28. **demande hors périmètre (juridique / médical)**

* **question** : `Donne-moi un avis juridique détaillé sur la garantie légale en Europe.`
* **attendu** : réponse très prudente + suggestion de consulter un expert (handover).

---

## K) performance & UX

29. **latence acceptable**

* **question** : `Liste des produits`
* **attendu** : réponse en moins de quelques secondes (selon connexion). Aucune duplication de messages.

30. **réinitialisation session**

* **action** : cliquer sur **Réinitialiser la conversation**, puis poser une nouvelle question.
* **attendu** : historique vidé, pas d'ancienne mémoire dans les réponses.

---

## bonus : jeux de prompts “clé en main”

* **vente rapide** :

  > `Je veux un SSD NVMe pour un usage bureautique, c'est quoi le meilleur rapport qualité/prix ?`
  > **attendu** : recommande 1 To à 100 €, propose de passer commande.

* **commande structurée** :

  > `Crée une commande pour 1 "PC Basic 8 Go" et 1 "Souris Gaming". Nom: Yao Kouadio, email: yao@ex.com, adresse: Cocody.`
  > **attendu** : message “Commande créée…” + montant `320.00 €`, stocks décrémentés.

* **support RAG** :

  > `Explique-moi la différence entre RAG et fine-tuning, d'après votre documentation.`
  > **attendu** : synthèse fidèle aux documents.

