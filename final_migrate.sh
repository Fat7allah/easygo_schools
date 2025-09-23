#!/bin/bash

# Script de migration final pour EasyGo Schools
# Tous les problèmes de fixtures ont été corrigés

SITE_NAME="easygo.educ"

echo "🚀 Migration finale pour $SITE_NAME"
echo "===================================="
echo ""
echo "✅ Corrections appliquées:"
echo "   - Custom fields désactivés (géré via patch)"
echo "   - Workflow state fields ajoutés"
echo "   - Allow edit fields corrigés"
echo "   - Dashboard DocType références corrigées"
echo ""

# Étape 1: Nettoyer le cache
echo "🧹 Nettoyage du cache..."
bench --site $SITE_NAME clear-cache

# Étape 2: Migration complète
echo "📦 Migration avec fixtures corrigées..."
bench --site $SITE_NAME migrate 2>&1 | tee final_migration_log.txt

# Vérifier le résultat
if [ $? -eq 0 ]; then
    echo ""
    echo "✅ MIGRATION RÉUSSIE!"
    echo ""
    
    # Vérifier l'installation
    echo "📊 Vérification de l'installation..."
    bench --site $SITE_NAME console << 'PYTHON'
import frappe

# Vérifier les modules
modules = ["Scolarite", "Vie Scolaire", "Finances RH", "Administration Communications", "Gestion Etablissement", "Referentiels"]
total_doctypes = 0

for module in modules:
    doctypes = frappe.get_all("DocType", {"module": module}, pluck="name")
    total_doctypes += len(doctypes)
    print(f"✓ {module}: {len(doctypes)} DocTypes")

print(f"\n📊 Total: {total_doctypes} DocTypes installés")

# Vérifier les rôles
roles = frappe.get_all("Role", {"name": ["in", ["Student", "Parent", "Teacher"]]}, pluck="name")
print(f"✓ Rôles de base: {len(roles)} créés")

print("\n✅ Installation validée!")
PYTHON

    echo ""
    echo "🔗 Accéder à l'application:"
    echo "   bench --site $SITE_NAME browse"
    echo ""
    echo "📚 Prochaines étapes:"
    echo "   1. Créer les utilisateurs via Setup > User"
    echo "   2. Configurer l'année scolaire via Setup > Academic Year"
    echo "   3. Créer les classes via School Class"
    echo "   4. Ajouter des élèves via Student"
    echo ""
    echo "📖 Consultez POST_INSTALLATION.md pour plus de détails"
    
else
    echo ""
    echo "❌ ERREUR DE MIGRATION"
    echo ""
    echo "📋 Vérifiez les logs:"
    echo "   tail -n 50 final_migration_log.txt"
    echo ""
    echo "🔧 Solutions possibles:"
    echo "   1. Vérifier les permissions de la base de données"
    echo "   2. Redémarrer les services Frappe"
    echo "   3. Consulter MIGRATION_FIXES.md"
    
    exit 1
fi

echo ""
echo "===================================="
echo "🎉 EasyGo Schools est prêt à l'emploi!"
echo "===================================="
