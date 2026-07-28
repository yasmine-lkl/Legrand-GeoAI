#!/usr/bin/env bash
# ============================================================
# Legrand GeoAI — Active le GPU NVIDIA pour Docker (Ollama)
# Installe le NVIDIA Container Toolkit puis branche le GPU sur Docker.
# Usage :  bash setup-gpu.sh
# (le script demandera votre mot de passe sudo une seule fois)
# ============================================================
set -euo pipefail

echo "==> 1/5  Vérification du pilote NVIDIA sur l'hôte..."
if ! command -v nvidia-smi >/dev/null 2>&1; then
  echo "ERREUR : nvidia-smi introuvable. Le pilote NVIDIA n'est pas installé." >&2
  exit 1
fi
nvidia-smi -L

echo "==> 2/5  Ajout du dépôt NVIDIA Container Toolkit..."
curl -fsSL https://nvidia.github.io/libnvidia-container/gpgkey \
  | sudo gpg --dearmor -o /usr/share/keyrings/nvidia-container-toolkit-keyring.gpg
curl -s -L https://nvidia.github.io/libnvidia-container/stable/deb/nvidia-container-toolkit.list \
  | sed 's#deb https://#deb [signed-by=/usr/share/keyrings/nvidia-container-toolkit-keyring.gpg] https://#g' \
  | sudo tee /etc/apt/sources.list.d/nvidia-container-toolkit.list >/dev/null

echo "==> 3/5  Installation du toolkit..."
sudo apt-get update
sudo apt-get install -y nvidia-container-toolkit

echo "==> 4/5  Configuration du runtime Docker + redémarrage du démon..."
sudo nvidia-ctk runtime configure --runtime=docker
sudo systemctl restart docker

echo "==> 5/5  Test : le GPU est-il visible dans un conteneur ?"
if docker run --rm --gpus all ubuntu:22.04 nvidia-smi -L; then
  echo
  echo "✅ SUCCÈS : Docker voit le GPU."
  echo "   Reviens dans Claude et dis 'done' — je relance Ollama sur GPU et je ré-ingère le PDF RTC360."
else
  echo
  echo "❌ Le GPU n'est toujours pas visible. Copie la sortie ci-dessus dans Claude." >&2
  exit 1
fi
