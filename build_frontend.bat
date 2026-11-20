cd frontend
cmd /c pnpm run build
cd ..
powershell "rm -Recurse .\backend\dist"
powershell "cp -Recurse .\frontend\dist .\backend\dist"
@pause