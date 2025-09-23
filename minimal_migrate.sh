#!/bin/bash

# Script de migration minimaliste pour EasyGo Schools
# Conçu pour éviter tous les conflits de fixtures

SITE_NAME="easygo.educ"

echo "🚀 Migration minimaliste pour $SITE_NAME"
echo "=========================================="
echo ""
echo "📌 Configuration actuelle:"
echo "   - Seuls les rôles basiques sont activés"
echo "   - Dashboards, Reports, Workflows désactivés"
echo "   - Custom fields gérés via patches"
echo ""

# Étape 1: Nettoyer le cache
echo "🧹 Nettoyage du cache..."
bench --site $SITE_NAME clear-cache

# Étape 2: Migration basique
echo "📦 Migration des DocTypes..."
bench --site $SITE_NAME migrate --skip-failing-patches

# Étape 3: Vérifier l'installation
echo "✅ Vérification de l'installation..."
if bench --site $SITE_NAME list-apps | grep -q easygo_schools; then
    echo "   ✓ EasyGo Schools installé"
else
    echo "   ✗ Erreur d'installation"
    exit 1
fi

echo ""
echo "=========================================="
echo "✅ Migration minimaliste terminée!"
echo ""
echo "📋 Prochaines étapes (manuellement):"
echo "   1. Activer les dashboards un par un"
echo "   2. Créer les workflows via l'interface"
echo "   3. Configurer les custom fields si nécessaire"
echo "   4. Importer les rôles additionnels"
echo ""
echo "🔗 Accéder à l'application:"
echo "   bench --site $SITE_NAME browse"
echo ""
