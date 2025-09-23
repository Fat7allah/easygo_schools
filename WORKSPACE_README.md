# 📋 Configuration des Workspaces - EasyGo Schools

## ⚠️ IMPORTANT - À LIRE

Les workspaces peuvent causer des problèmes de routing dans Frappe Framework. Si vous rencontrez l'erreur **"La ressource que vous recherchez n'est pas disponible"**, suivez ces instructions.

## État Actuel

- **107 DocTypes** répartis dans **6 Workspaces**
- Tous les doctypes sont correctement listés dans `workspace.json`
- Configuration simplifiée sans contenu complexe pour éviter les erreurs

## Distribution des DocTypes par Module

| Module | Nombre de DocTypes | Statut |
|--------|-------------------|---------|
| **Scolarité** | 35 | ✅ Complet |
| **Vie Scolaire** | 15 | ✅ Complet |
| **Finances & RH** | 23 | ✅ Complet |
| **Administration & Communications** | 16 | ✅ Complet |
| **Gestion Établissement** | 16 | ✅ Complet |
| **Référentiels** | 2 | ✅ Complet |
| **TOTAL** | **107** | ✅ |

## Navigation Alternative (Recommandée)

Si les workspaces causent des problèmes, utilisez ces méthodes alternatives :

### 1. Module Definer
```
Setup → Module Definer
```

### 2. Recherche Globale
```
Ctrl + G (ou Cmd + G sur Mac)
```

### 3. URLs Directes
Accédez directement aux DocTypes via leurs URLs :
- `/app/student` - Liste des élèves
- `/app/fee-bill` - Factures de frais
- `/app/employee` - Liste des employés
- `/app/student-attendance` - Présences
- `/app/canteen-menu` - Menus de cantine
- etc.

## Activation/Désactivation des Workspaces

### Pour DÉSACTIVER les workspaces :
```bash
# Renommer le fichier
mv easygo_schools/fixtures/workspace.json easygo_schools/fixtures/workspace.json.disabled

# Modifier hooks.py et retirer "workspace" de la liste fixtures
```

### Pour ACTIVER les workspaces :
```bash
# Restaurer le fichier
mv easygo_schools/fixtures/workspace.json.disabled easygo_schools/fixtures/workspace.json

# Modifier hooks.py et ajouter "workspace" dans la liste fixtures
```

## Liste Complète des DocTypes par Module

### 📚 Module Scolarité (35 DocTypes)
1. Academic Term
2. Academic Year
3. Assessment
4. Assessment Plan
5. Class Subject Teacher
6. Course Schedule
7. Exam
8. Grade
9. Grading Scale
10. Guardian
11. Homework
12. Homework Attachment
13. Homework Submission
14. Learning Sequence
15. Learning Sequence Lesson
16. Lesson Log
17. Lesson Plan
18. Orientation Choice
19. Orientation Meeting
20. Orientation Plan
21. Placement Test
22. Placement Test Attachment
23. Placement Test Result
24. Program
25. Report Card
26. Report Card Subject
27. Resource
28. School Class
29. Student
30. Student Academic History
31. Student Follow Up
32. Student Group
33. Student Group Member
34. Student Transfer
35. Subject

### 🏫 Module Vie Scolaire (15 DocTypes)
1. Accident Report
2. Accident Report Attachment
3. Activity Enrollment
4. Activity Registration
5. Activity Schedule
6. Attendance Justification
7. Disciplinary Action
8. Extracurricular Activity
9. Health Record
10. Intervention Session
11. Medical Visit
12. Remedial Plan
13. Student Attendance
14. Support Trigger Rule
15. Vaccination Record

### 💰 Module Finances & RH (23 DocTypes)
1. Budget
2. Budget Line
3. Contract
4. Employee
5. Expense Entry
6. Fee Bill
7. Fee Installment
8. Fee Item
9. Fee Structure
10. Fee Type
11. HR Attendance
12. Installment Plan
13. Leave Application
14. Leave Type
15. Payment Entry
16. Payroll Cycle
17. Receipt Print
18. Salary Component
19. Salary Slip
20. Salary Structure
21. School Account
22. School Cost Center
23. School Ledger

### 📢 Module Administration & Communications (16 DocTypes)
1. Communication Log
2. Consent Detail
3. Correspondence
4. Document Template
5. Meeting Request
6. Message
7. Message Attachment
8. Message Participant
9. Message Read Receipt
10. Message Thread
11. Message Thread Participant
12. Notification Rule
13. Notification Template
14. Parent Consent
15. Rectorate Correspondence
16. School Communication

### 🏢 Module Gestion Établissement (16 DocTypes)
1. Canteen Menu
2. Canteen Menu Item
3. Equipment
4. Maintenance Request
5. Meal Order
6. Purchase Order
7. Purchase Request
8. Room
9. School Asset
10. Stock Entry
11. Stock Item
12. Stock Ledger
13. Transport Route
14. Transport Stop
15. Transport Student
16. Work Order

### 📊 Module Référentiels (2 DocTypes)
1. Reference Data Item
2. Reference Table

## Résolution des Problèmes

### Erreur : "La ressource que vous recherchez n'est pas disponible"
**Causes possibles :**
- Le workspace essaie de router vers une page inexistante
- Le DocType n'a pas les permissions appropriées
- Le module n'est pas correctement installé

**Solutions :**
1. Utiliser la navigation alternative (Module Definer ou Global Search)
2. Vérifier les permissions du DocType
3. Exécuter `bench --site [site-name] migrate`
4. Désactiver temporairement les workspaces

### Erreur : DocType non trouvé dans le workspace
**Solution :**
```bash
# Régénérer les workspaces
python generate_complete_workspaces.py

# Vérifier la cohérence
python verify_workspace_doctypes.py
```

## Scripts Utiles

- **`generate_complete_workspaces.py`** : Génère automatiquement workspace.json avec tous les doctypes
- **`verify_workspace_doctypes.py`** : Vérifie la cohérence entre les doctypes et les workspaces

---

**Note Importante** : Les workspaces sont optionnels dans Frappe. L'application fonctionnera parfaitement sans eux en utilisant la navigation standard.
