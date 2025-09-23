# 📋 Guide de Configuration Post-Installation

## ✅ État Après Migration Minimaliste

Après avoir exécuté `minimal_migrate.sh`, votre installation contient :

- **107 DocTypes** installés et fonctionnels
- **3 Rôles de base** : Student, Parent, Teacher
- **Aucune fixture** activée (pour éviter les conflits)

## 🔧 Configuration Manuelle Requise

### 1. Créer les Rôles Additionnels

Dans **Setup > Role**, créer :

- `School Administrator` - Administrateur de l'école
- `Principal` - Directeur
- `Accountant` - Comptable
- `HR Manager` - Responsable RH
- `Maintenance` - Maintenance
- `Accounts User` - Utilisateur Comptabilité
- `Accounts Manager` - Manager Comptabilité
- `HR User` - Utilisateur RH
- `Facility Manager` - Gestionnaire des installations

### 2. Configurer les Custom Fields MASSAR

Exécuter dans la console :

```bash
bench --site easygo.educ console

# Puis exécuter :
from easygo_schools.patches.v1_add_massar_fields import execute
execute()
```

### 3. Activer les Dashboards

#### Corriger et activer dans hooks.py :

```python
fixtures = [
    "dashboard_chart",  # Réactiver après correction
    {
        "doctype": "Role",
        # ... rôles ...
    }
]
```

Puis :
```bash
bench --site easygo.educ migrate
```

### 4. Configurer les Workflows Manuellement

Aller dans **Setup > Workflow** et créer :

#### Workflow Admission Élève

**États** :
- Application Reçue (Draft)
- En Révision (Draft)
- Approuvé (Submitted)
- Rejeté (Draft)

**Transitions** :
- Application Reçue → En Révision
- En Révision → Approuvé
- En Révision → Rejeté

#### Workflow Congés

**États** :
- Ouvert (Draft)
- Appliqué (Draft)
- Approuvé (Submitted)
- Rejeté (Draft)

### 5. Configurer les Reports

Les reports peuvent être activés dans hooks.py :

```python
fixtures = [
    "dashboard_chart",
    "report",  # Ajouter
    # ...
]
```

### 6. Importer les Property Setters

Pour les séries de numérotation automatiques :

```bash
bench --site easygo.educ console

# Créer les naming series
import frappe

# Student
frappe.db.set_value("DocType", "Student", "autoname", "STU-.YYYY.-")

# Employee
frappe.db.set_value("DocType", "Employee", "autoname", "EMP-.YYYY.-")

# School Class
frappe.db.set_value("DocType", "School Class", "autoname", "CLS-.YYYY.-")

# Fee Bill
frappe.db.set_value("DocType", "Fee Bill", "autoname", "FB-.YYYY.-")

# Salary Slip
frappe.db.set_value("DocType", "Salary Slip", "autoname", "SS-.YYYY.-")

frappe.db.commit()
```

### 7. Configurer les Web Forms

Dans **Website > Web Form**, créer :

- Student Admission Application
- Attendance Justification
- Parent Consent Form
- Meeting Request
- Transport Registration

### 8. Configuration des Paramètres

#### School Settings
**Setup > School Settings** :
- Nom de l'école
- Code GRESA
- Année scolaire active
- Logo

#### Finance Settings
**Setup > Finance Settings** :
- Devise par défaut : MAD
- Format de date : dd/mm/yyyy
- Début année fiscale : 01 Septembre

## 🎯 Ordre de Priorité

1. **Immédiat** : Créer les rôles additionnels
2. **Important** : Configurer les custom fields MASSAR
3. **Recommandé** : Activer les dashboards
4. **Optionnel** : Configurer workflows et web forms

## ✨ Vérification Finale

```bash
# Vérifier tous les modules
bench --site easygo.educ console

>>> import frappe
>>> # Vérifier un DocType
>>> frappe.get_meta("Student")

>>> # Lister tous les DocTypes du module
>>> frappe.get_all("DocType", {"module": "Scolarite"}, pluck="name")

>>> # Vérifier les custom fields
>>> frappe.get_all("Custom Field", {"dt": "Student"}, ["fieldname", "label"])
```

## 🆘 En Cas de Problème

### Erreur "DocType not found"

```bash
# Reconstruire le cache
bench --site easygo.educ clear-cache
bench --site easygo.educ build
```

### Erreur de permissions

```bash
# Reconstruire les permissions
bench --site easygo.educ build-permissions
```

### Reset complet (ATTENTION : supprime les données)

```bash
bench --site easygo.educ reinstall
bench --site easygo.educ install-app easygo_schools
```

## 📌 Checklist Finale

- [ ] Rôles créés
- [ ] Custom fields MASSAR configurés
- [ ] Au moins un utilisateur par rôle créé
- [ ] Année scolaire active configurée
- [ ] Une classe test créée
- [ ] Un élève test créé
- [ ] Navigation testée (Module Definer)
- [ ] Permissions vérifiées

---

**Date** : 23 Septembre 2025  
**Version** : 1.0.0  
**Support** : support@easygo-schools.ma
