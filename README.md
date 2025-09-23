# 🎓 EasyGo Schools - Système de Gestion d'Établissements Scolaires

![Version](https://img.shields.io/badge/version-1.0.0-blue)
![Frappe](https://img.shields.io/badge/frappe-v15-green)
![License](https://img.shields.io/badge/license-MIT-purple)
![Language](https://img.shields.io/badge/language-FR%2FAR-orange)

**EasyGo Schools** est une application complète de gestion d'établissements scolaires pour le Maroc, développée sur Frappe Framework v15. Conforme aux standards du ministère de l'Éducation nationale marocain et compatible avec le système MASSAR.

## 🌟 Fonctionnalités Principales

### 📚 Module Scolarité
- Gestion complète des élèves et enseignants
- Inscription et réinscription automatisées
- Emplois du temps dynamiques
- Système d'évaluation et bulletins
- Orientation scolaire
- Support des codes MASSAR et CNE

### 🏫 Module Vie Scolaire
- Suivi de présence en temps réel
- Gestion disciplinaire avec workflows
- Dossiers médicaux et suivi santé
- Activités parascolaires
- Plans de soutien personnalisés

### 💰 Module Finances & RH
- Gestion des frais de scolarité
- Paiements échelonnés
- Paie automatisée du personnel
- Gestion budgétaire complète
- Intégration comptable

### 📢 Module Administration & Communication
- Messagerie interne multi-canaux
- Notifications automatiques
- Correspondance administrative
- Consentements parentaux numériques
- Modèles de documents

### 🏢 Module Gestion Établissement
- Gestion de la cantine (menus, réservations)
- Transport scolaire avec circuits
- Maintenance et équipements
- Gestion des stocks
- Planification des ressources

### 📊 Module Référentiels
- Données de référence centralisées
- Configuration des niveaux scolaires
- Gestion des matières et programmes
- Calendrier académique

## 📈 Statistiques de l'Application

- **107 DocTypes** organisés en 6 modules
- **13 Rapports** préconfigurés
- **6 Tableaux de bord** interactifs
- **5 Workflows** automatisés
- **3 Portails** (Élève, Parent, Enseignant)
- **Support bilingue** (Français/Arabe)

## 🚀 Installation

### Prérequis
- Frappe Framework v15.x
- Python 3.10+
- Node.js 18+
- MariaDB/MySQL
- Redis Server

### Installation Rapide

```bash
# Créer un nouveau site
bench new-site ecole.local

# Obtenir l'application
bench get-app file:///chemin/vers/easygo_schools

# Installer dans le site
bench --site ecole.local install-app easygo_schools

# Migrer la base de données
bench --site ecole.local migrate

# Démarrer
bench --site ecole.local browse
```

## 🔧 Configuration

### Configuration Initiale
1. Accéder à **Setup > School Settings**
2. Configurer l'année scolaire active
3. Créer les utilisateurs et assigner les rôles
4. Configurer les workflows nécessaires

### Rôles Disponibles
- School Administrator
- Teacher
- Student
- Parent
- HR Manager
- Accounts Manager
- Facility Manager

## 📱 Portails Utilisateurs

| Portail | URL | Fonctionnalités |
|---------|-----|-----------------|
| **Élève** | `/student` | Notes, emploi du temps, bulletins |
| **Parent** | `/parent` | Suivi présence, frais, communications |
| **Enseignant** | `/teacher` | Gestion cours, évaluations, présences |

## 🔄 Workflows Intégrés

1. **Admission des Élèves** : Application → Review → Approved/Rejected
2. **Validation Paiements** : Draft → Pending → Approved
3. **Congés Personnel** : Open → Applied → Approved/Rejected
4. **Actions Disciplinaires** : Reported → Investigation → Action
5. **Maintenance** : Requested → In Progress → Completed

## 📊 Rapports et Analytics

### Rapports Disponibles
- Liste des élèves avec filtres avancés
- Résumé de présence par classe
- État de recouvrement des frais
- Résultats d'évaluations
- Performance par matière
- Synthèse RH et paie

### Tableaux de Bord
- Tendance des inscriptions
- Taux de présence temps réel
- Statut des paiements
- Distribution des notes
- Effectifs par département
- Revenus mensuels

## 🔐 Sécurité et Conformité

- ✅ Conforme aux normes MASSAR
- ✅ Support des identifiants nationaux (CIN, CNE)
- ✅ Chiffrement des données sensibles
- ✅ Audit trail complet
- ✅ Permissions granulaires par rôle
- ✅ Sauvegarde automatique

## ⚠️ Notes Importantes

### Navigation
Suite à des problèmes de routing avec les workspaces, utilisez :
- **Module Definer** : Setup > Module Definer
- **Recherche Globale** : Ctrl+G
- **URLs Directes** : /app/student, /app/fee-bill

### Performance
- Cache Redis activé par défaut
- Optimisation pour 5000+ élèves
- Support de requêtes concurrentes

## 🛠️ Développement

### Structure du Projet
```
easygo_schools/
├── scolarite/           # Module Scolarité
├── vie_scolaire/        # Module Vie Scolaire
├── finances_rh/         # Module Finances & RH
├── administration_communications/  # Communications
├── gestion_etablissement/  # Gestion Infrastructure
├── referentiels/        # Données de référence
├── api/                 # Endpoints REST
├── fixtures/            # Données de configuration
├── patches/             # Migrations
└── translations/        # Traductions FR/AR
```

### Commandes Utiles

```bash
# Mode développeur
bench --site ecole.local set-config developer_mode 1

# Tests
bench --site ecole.local run-tests

# Backup
bench --site ecole.local backup

# Mise à jour
bench update --apps easygo_schools
```

## 📚 Documentation

- [Guide de Démarrage Rapide](GUIDE_DEMARRAGE_RAPIDE.md)
- [Rapport de Conformité](RAPPORT_CONFORMITE_FRAPPE.md)
- [Documentation Frappe](https://frappeframework.com/docs)

## 🤝 Contribution

Ce projet utilise `pre-commit` pour le formatage et le linting du code :

```bash
cd apps/easygo_schools
pre-commit install
```

Outils configurés :
- ruff (Python linting)
- eslint (JavaScript linting)
- prettier (formatage)
- pyupgrade (modernisation Python)

## 📝 License

MIT License - Voir [LICENSE](LICENSE) pour plus de détails.

## 💬 Support

- **Email** : support@easygo-education.ma
- **Forum** : [Discuss Frappe](https://discuss.frappe.io)
- **Issues** : [GitHub Issues](https://github.com/yourusername/easygo_schools/issues)

## 🏆 Crédits

Développé par l'équipe EasyGo Education Team pour moderniser la gestion des établissements scolaires au Maroc.

---

**Version** : 1.0.0  
**Compatible avec** : Frappe Framework v15.x  
**Dernière mise à jour** : Septembre 2025
