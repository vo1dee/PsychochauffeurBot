#!/bin/bash
# Restart the PsychoChauffeur bot service

echo "Restarting psychochauffeur-bot service..."
sudo systemctl restart psychochauffeur-bot.service

echo "Checking service status..."
sudo systemctl status psychochauffeur-bot.service --no-pager

echo "Done!"
