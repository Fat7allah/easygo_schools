#!/bin/bash

# Script de migration sûr pour EasyGo Schools
# Ce script gère les erreurs de migration communes

SITE_NAME="easygo.educ"

echo "🚀 Démarrage de la migration sûre pour $SITE_NAME"
echo "============================================"

# Étape 1: Vider le cache
echo "📦 Étape 1: Nettoyage du cache..."
bench --site $SITE_NAME clear-cache

# Étape 2: Tenter la migration
echo "🔧 Étape 2: Tentative de migration..."
bench --site $SITE_NAME migrate 2>&1 | tee migration_log.txt

# Vérifier si la migration a échoué à cause des custom fields
if grep -q "already exists" migration_log.txt; then
    echo "⚠️  Détecté: Conflit de custom fields"
    echo "📝 Application du patch de correction..."
    
    # Exécuter le patch directement
    bench --site $SITE_NAME execute easygo_schools.patches.v1_add_massar_fields.execute
    
    echo "✅ Patch appliqué"
fi

# Étape 3: Reconstruire les permissions
echo "🔐 Étape 3: Reconstruction des permissions..."
bench --site $SITE_NAME build-permissions

# Étape 4: Reconstruire l'index de recherche
echo "🔍 Étape 4: Reconstruction de l'index de recherche..."
bench --site $SITE_NAME rebuild-index

# Étape 5: Vérifier l'installation
echo "✨ Étape 5: Vérification de l'installation..."
bench --site $SITE_NAME list-apps | grep easygo_schools

if [ $? -eq 0 ]; then
    echo "✅ EasyGo Schools est installé avec succès!"
else
    echo "❌ Erreur: EasyGo Schools n'est pas installé"
    exit 1
fi

echo ""
echo "============================================"
echo "✅ Migration terminée!"
echo ""
echo "📌 Notes importantes:"
echo "   - Les custom fields MASSAR ont été gérés via patch"
echo "   - Les workflows doivent être configurés manuellement"
echo "   - Les workspaces sont désactivés (utiliser Module Definer)"
echo ""
echo "🔗 Pour accéder à l'application:"
echo "   bench --site $SITE_NAME browse"
echo ""
