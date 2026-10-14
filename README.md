# Clínica Santa Aurora · Sistema de turnos

Aplicación didáctica para organizar la atención de una clínica. Incluye una consola de recepción y una pantalla para la sala de espera.

## Proyecto publicado

- Aplicación: https://clinica-turnos-santa-aurora.vercel.app/
- Repositorio público: https://github.com/manxxnxvarrete-commits/clinica-turnos-santa-aurora
- Vercel despliega automáticamente los cambios que llegan a `main`.

## Funciones

- Genera turnos consecutivos como **A01**, **A02** y elige entre consulta general, laboratorio, farmacia e imagenología.
- Muestra la fila en orden de llegada y permite asignar el siguiente turno a cualquiera de las cuatro ventanillas.
- Cada ventanilla puede marcarse ocupada o disponible. Al finalizar una atención, se libera y llama automáticamente al turno siguiente.
- La pantalla de sala se actualiza en vivo y muestra el turno llamado, la ventanilla y los lugares ocupados.
- Incluye aviso sonoro y anuncio de voz en español. Activa el sonido desde la pantalla para permitir la reproducción del navegador.
- Guarda la información en SQLite al trabajar localmente. Para una publicación compartida, admite PostgreSQL mediante la variable DATABASE_URL.

La aplicación no pide nombres ni datos médicos. Es un prototipo escolar sin inicio de sesión; no debe usarse para gestionar pacientes reales.

### Persistencia en la demo publicada

El despliegue actual no tiene una base PostgreSQL configurada. En Vercel usa SQLite temporal, por lo que los turnos pueden reiniciarse y no se garantiza que varias instancias compartan el mismo estado. Para una demostración consistente con varias pantallas, configura `DATABASE_URL` con una base PostgreSQL antes de usarla. No guardes datos reales de pacientes en esta demo.

## Ejecutar en Windows

Abre una terminal en la carpeta del proyecto y prepara Flask:

    python -m venv .venv
    .\.venv\Scripts\Activate.ps1
    python -m pip install -r requirements.txt
    python app.py

En otra terminal, instala y ejecuta Angular:

    cd frontend
    npm ci
    npm start

Abre http://localhost:4200. Angular envía las solicitudes /api a Flask en http://127.0.0.1:5000.

## Publicar en Vercel

El proyecto tiene una compilación de Angular que copia el sitio a public/, mientras Flask expone el API desde app.py. Vercel detecta Flask y conserva los archivos de public/ como contenido estático.

El repositorio ya está conectado al proyecto de Vercel. El script `build_frontend.py` instala dependencias y compila Angular durante cada despliegue. Para habilitar persistencia compartida, agrega `DATABASE_URL` en la configuración del proyecto de Vercel con la cadena de una base PostgreSQL.

También puedes desplegar desde una terminal con sesión iniciada en Vercel:

    npx vercel
    npx vercel --prod

## Publicar cambios en GitHub

    git add .
    git commit -m "Describe el cambio"
    git push origin main

Vercel iniciará el siguiente despliegue al recibir los cambios de `main`.
