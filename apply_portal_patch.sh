#!/bin/bash
git add .
git commit -m "fix(portal): handle Odoo monorepos/collections by scanning and symlinking modules"
git push origin 18.0
git checkout main
git merge 18.0
git push origin main
git checkout 18.0
