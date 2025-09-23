# 🚀 Guide de Démarrage Rapide - EasyGo Schools

## Installation de l'Application

### Prérequis
- Frappe Framework v15.x installé
- MariaDB ou MySQL configuré
- Python 3.10+
- Node.js 18+
- Redis Server

### Installation Étape par Étape

#### 1. Créer un nouveau site Frappe
```bash
bench new-site ecole.local
# Entrer le mot de passe administrateur quand demandé
```

#### 2. Installer l'application EasyGo Schools
```bash
# Ajouter l'application au bench
bench get-app file:///chemin/vers/easygo_schools

# Installer dans le site
bench --site ecole.local install-app easygo_schools

# Migrer la base de données
bench --site ecole.local migrate
```

#### 3. Configuration initiale
```bash
# Se connecter en tant qu'Administrator
bench --site ecole.local browse

# Identifiants par défaut
# Email: Administrator
# Mot de passe: [celui défini à l'étape 1]
```

---

## 🎓 Configuration de Base

### 1. Paramètres de l'École
1. Aller dans **Setup > School Settings**
2. Configurer :
   - Nom de l'établissement
   - Code GRESA
   - Adresse et contacts
   - Année scolaire active
   - Logo de l'école

### 2. Création de l'Année Scolaire
1. Aller dans **Scolarité > Academic Year**
2. Créer nouvelle année (ex: 2024-2025)
3. Définir les trimestres/semestres

### 3. Configuration des Rôles et Utilisateurs
1. **Créer les utilisateurs clés** :
   - Directeur (School Administrator)
   - Comptable (Accounts Manager)  
   - RH (HR Manager)
   - Enseignants (Teacher)

2. **Assigner les permissions** via Setup > Role Permission Manager

---

## 📊 Modules Principaux

### Module Scolarité
**Workflow d'inscription d'un élève :**
1. **Student** > Nouveau
2. Remplir les informations :
   - Code MASSAR (si disponible)
   - Informations personnelles
   - Guardian (Tuteur)
3. Créer un **Student Group** (Classe)
4. Affecter l'élève au groupe

### Module Vie Scolaire
**Gestion quotidienne :**
- **Student Attendance** : Prise de présence
- **Disciplinary Action** : Suivi disciplinaire
- **Health Record** : Dossier médical
- **Extracurricular Activity** : Activités parascolaires

### Module Finances & RH
**Gestion des frais :**
1. Créer une **Fee Structure** 
2. Générer les **Fee Bill** pour les élèves
3. Enregistrer les **Payment Entry**

**Gestion du personnel :**
1. Créer un **Employee**
2. Définir le **Contract**
3. Configurer la **Salary Structure**
4. Générer les **Salary Slip**

### Module Administration & Communication
- **Message Thread** : Messagerie interne
- **Notification Template** : Modèles de notification
- **Parent Consent** : Consentements parentaux

### Module Gestion Établissement
- **Canteen Menu** : Gestion de la cantine
- **Transport Route** : Circuits de transport
- **Maintenance Request** : Demandes de maintenance
- **Stock Item** : Gestion du matériel

---

## 🔄 Workflows Configurés

### 1. Admission des Élèves
```
Application Received → Under Review → Approved/Rejected
```

### 2. Validation des Paiements
```
Draft → Pending Approval → Approved/Cancelled
```

### 3. Congés du Personnel
```
Open → Applied → Approved/Rejected
```

### 4. Actions Disciplinaires
```
Reported → Under Investigation → Action Taken/Dismissed
```

### 5. Maintenance
```
Requested → In Progress → Completed
```

---

## 📈 Tableaux de Bord et Rapports

### Dashboards Disponibles
- Student Enrollment Trend
- Student Attendance Rate  
- Fee Collection Status
- Assessment Results Distribution
- Employee Count by Department
- Monthly Revenue Trend

### Rapports Principaux
- Student List Report
- Attendance Summary Report
- Fee Collection Report
- Assessment Results Report
- Employee Summary Report
- Course Schedule Report

---

## 🌐 Portails Utilisateurs

### Portal Élève
- URL : `/student`
- Consultation notes et emploi du temps
- Téléchargement bulletins
- Messages

### Portal Parent
- URL : `/parent`
- Suivi de présence
- Consultation des frais
- Communication avec l'école

### Portal Enseignant  
- URL : `/teacher`
- Gestion des cours
- Saisie des notes
- Prise de présence

---

## ⚡ Commandes Utiles

### Maintenance
```bash
# Sauvegarder le site
bench --site ecole.local backup

# Mettre à jour l'application
bench update --apps easygo_schools

# Réindexer la recherche
bench --site ecole.local rebuild-index

# Vider le cache
bench --site ecole.local clear-cache
```

### Développement
```bash
# Mode développeur
bench --site ecole.local set-config developer_mode 1

# Console Python
bench --site ecole.local console

# Logs en temps réel
bench start
```

---

## 🔧 Résolution des Problèmes Courants

### Erreur : "La ressource n'est pas disponible"
**Solution** : Utiliser la navigation standard
- Module Definer (Setup > Module Definer)
- Recherche globale (Ctrl+G)
- URLs directes (/app/student)

### Erreur : Permissions insuffisantes
**Solution** : Vérifier dans Role Permission Manager que l'utilisateur a les bonnes permissions

### Erreur : Workflow non déclenché
**Solution** : Vérifier que le workflow est actif dans Setup > Workflow

### Performance lente
**Solutions** :
1. Optimiser les index de base de données
2. Activer le cache Redis
3. Limiter le nombre de rapports simultanés

---

## 📞 Support et Documentation

### Ressources
- Documentation Frappe : https://frappeframework.com/docs
- Forum Frappe : https://discuss.frappe.io
- GitHub du projet : [Votre repo GitHub]

### Contacts Support
- Email : support@easygo-schools.ma
- Téléphone : +212 XXX XXX XXX

---

## 🎯 Check-list Post-Installation

- [ ] Configurer les paramètres de l'école
- [ ] Créer l'année scolaire active
- [ ] Importer les données de base (niveaux, matières)
- [ ] Créer les utilisateurs principaux
- [ ] Configurer les workflows
- [ ] Tester les permissions par rôle
- [ ] Configurer les sauvegardes automatiques
- [ ] Former les utilisateurs clés
- [ ] Documenter les procédures spécifiques

---

**Version** : 1.0.0  
**Date** : Septembre 2025  
**Compatible avec** : Frappe Framework v15.x
