# FallAlert APK Download Directory

Place `fallalert.apk` in this directory. 
The Nginx Gateway serves files in this directory at `http://<SERVER-IP>/download/fallalert.apk`.

If `FallAlert/app/build/outputs/apk/debug/app-debug.apk` exists, `deploy-aws.sh` automatically copies it here before starting Docker.
