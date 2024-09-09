@echo off
cd "C:\Users\aaleksan\OneDrive - Amplifon S.p.A\Documentos\python_alisa\MBreport\MBreportapp"
git add mbreport_query_new.xlsx
git commit -m "Automatic dataset update"
git push origin main
exit /b 0
