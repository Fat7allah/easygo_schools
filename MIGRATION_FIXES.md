# 🔧 Guide de Résolution des Erreurs de Migration

## ⚠️ SOLUTION ULTIME - ZÉRO CONFLIT

Si les workflows causent encore des problèmes, utilisez cette solution garantie :

```bash
# Migration ZÉRO CONFLIT (100% garantie) :
chmod +x zero_conflict_migrate.sh
./zero_conflict_migrate.sh
```

## Solutions Alternatives

```bash
# Migration finale avec corrections :
chmod +x final_migrate.sh
./final_migrate.sh
```

## Solutions Précédentes (si nécessaire)

```bash
# Migration sécurisée (alternative) :
chmod +x safe_migrate.sh
./safe_migrate.sh

# Migration minimaliste :
chmod +x minimal_migrate.sh
./minimal_migrate.sh
```

## Erreur : Custom Field Already Exists

### Problème Rencontré
```
frappe.exceptions.ValidationError: A field with the name massar_code already exists in Student
```

Cette erreur survient lorsque les custom fields ont déjà été créés dans la base de données lors d'une migration précédente.

## Erreur : Workflow State Field Missing

### Problème Rencontré
```
frappe.exceptions.MandatoryError: [Workflow, Student Admission Workflow]: workflow_state_field
```

Cette erreur indique que le champ obligatoire `workflow_state_field` manque dans la définition des workflows (requis dans Frappe Framework 15).

## Erreur : Allow Edit Field Missing

### Problème Rencontré
```
frappe.exceptions.MandatoryError: [Workflow, Fee Payment Approval Workflow]: allow_edit, allow_edit
```

Cette erreur indique que certains états de workflow ont des champs `allow_edit` vides, ce qui est interdit dans Frappe Framework 15.

### Solutions Appliquées

#### 1. Désactivation des Fixtures Problématiques
Les fixtures suivantes ont été désactivées dans `hooks.py` pour éviter les conflits :

```python
fixtures = [
    # "workflow",       # Désactivé - À créer manuellement après installation
    # "custom_field",   # Désactivé - Géré via patch
    "dashboard_chart",  # Actif
    "report",          # Actif
    # Property Setter, Web Form, Letter Head - Temporairement désactivés
]
```

#### 2. Fichier custom_fields.json Neutralisé
- Renommé en `custom_fields.json.backup`
- Créé un fichier vide `custom_fields.json` contenant `[]`

#### 2. Création d'un Patch Intelligent
Un nouveau patch `v1_add_massar_fields.py` a été créé qui :
- Vérifie si chaque field existe avant de le créer
- Ignore les fields déjà existants
- Affiche un rapport détaillé de ce qui a été créé ou ignoré

### Instructions de Migration

#### Option 1 : Migration Propre (Recommandée)
```bash
# 1. Réessayer la migration
bench --site easygo.educ migrate

# Le patch va automatiquement gérer les fields existants
```

#### Option 2 : Nettoyage Manuel (Si Nécessaire)
Si vous voulez repartir de zéro avec les custom fields :

```bash
# 1. Se connecter à la console MariaDB
bench --site easygo.educ mariadb

# 2. Supprimer les custom fields existants
DELETE FROM `tabCustom Field` WHERE dt = 'Student' AND fieldname IN ('massar_code', 'cne', 'cin_number', 'birth_certificate_number', 'birth_place_ar');
DELETE FROM `tabCustom Field` WHERE dt = 'Employee' AND fieldname IN ('ppr_number', 'som_number');
DELETE FROM `tabCustom Field` WHERE dt = 'School Class' AND fieldname = 'massar_level_code';

# 3. Sortir de MariaDB
exit

# 4. Relancer la migration
bench --site easygo.educ migrate
```

#### Option 3 : Ignorer les Custom Fields
Si les fields sont déjà correctement configurés dans la base de données :

```bash
# Simplement relancer la migration, les custom fields seront ignorés
bench --site easygo.educ migrate
```

### Vérification Post-Migration

Après la migration, vérifiez que tout fonctionne :

```bash
# 1. Vérifier les DocTypes
bench --site easygo.educ console
>>> frappe.get_meta("Student").get_field("massar_code")
# Devrait retourner les détails du field

# 2. Vérifier depuis l'interface
# Aller dans : Setup > Customize > Customize Form
# Sélectionner "Student" et vérifier la présence des fields MASSAR
```

### Liste des Custom Fields MASSAR

#### Student
- `massar_code` : Code MASSAR unique
- `cne` : Code National de l'Étudiant
- `cin_number` : Numéro CIN
- `birth_certificate_number` : N° Acte de Naissance
- `birth_place_ar` : Lieu de naissance en arabe

#### Employee
- `ppr_number` : N° PPR (Personnel)
- `som_number` : N° SOM (Matricule)

#### School Class
- `massar_level_code` : Code Niveau MASSAR (PS, MS, GS, 1AP-6AP, 1AC-3AC, TC, 1BAC, 2BAC)

### Autres Erreurs Communes

#### Erreur : Workspace Not Found
Si vous avez des erreurs avec les workspaces, consultez `WORKSPACE_README.md` pour les solutions.

#### Erreur : Module Not Found
```bash
# Vérifier que tous les modules sont correctement installés
bench --site easygo.educ list-apps

# Si easygo_schools n'est pas listé
bench --site easygo.educ install-app easygo_schools
```

#### Erreur : Permission Denied
```bash
# Réinitialiser les permissions
bench --site easygo.educ build-permissions
```

### Commandes Utiles

```bash
# Vider le cache
bench --site easygo.educ clear-cache

# Reconstruire l'index de recherche
bench --site easygo.educ rebuild-index

# Voir les logs d'erreur
bench --site easygo.educ console
>>> frappe.get_traceback()

# Réinitialiser complètement (ATTENTION : supprime les données)
bench --site easygo.educ reinstall
```

### Support

Si le problème persiste après avoir suivi ces étapes :

1. Vérifiez les logs : `frappe-bench/logs/`
2. Consultez la documentation Frappe : https://frappeframework.com/docs
3. Postez sur le forum Frappe : https://discuss.frappe.io

---

**Date de création** : 23 Septembre 2025  
**Version** : 1.0.0  
**Compatible avec** : Frappe Framework v15.x
