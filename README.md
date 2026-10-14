# Clínica Santa Aurora · Sistema de turnos

Aplicación didáctica para organizar la atención de una clínica. Incluye una consola de recepción y una pantalla para la sala de espera.

## Funciones

- Genera turnos consecutivos como **A01**, **A02** y elige entre consulta general, laboratorio, farmacia e imagenología.
- Muestra la fila en orden de llegada y permite asignar el siguiente turno a cualquiera de las cuatro ventanillas.
- Cada ventanilla puede marcarse ocupada o disponible. Al finalizar una atención, se libera y llama automáticamente al turno siguiente.
- La pantalla de sala se actualiza en vivo y muestra el turno llamado, la ventanilla y los lugares ocupados.
- Incluye aviso sonoro y anuncio de voz en español. Activa el sonido desde la pantalla para permitir la reproducción del navegador.
- Guarda la información en SQLite al trabajar localmente. Para una publicación compartida, admite PostgreSQL mediante la variable DATABASE_URL.

La aplicación no pide nombres ni datos médicos. Es un prototipo escolar sin inicio de sesión; no debe usarse para gestionar pacientes reales.

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

1. Crea o conecta un repositorio Git y elige la carpeta raíz clinica-turnos como proyecto de Vercel.
2. En la configuración de Vercel, agrega DATABASE_URL con la cadena de conexión de una base PostgreSQL compartida.
3. Despliega el proyecto. El script build_frontend.py instala dependencias y compila Angular durante la compilación de Vercel.

El archivo SQLite que se usa como alternativa local dentro de Vercel vive en almacenamiento temporal y no sirve como base de datos compartida. Configura PostgreSQL para que recepción y sala vean los mismos turnos aunque las funciones se reinicien.

También puedes desplegar desde una terminal con sesión iniciada en Vercel:

    npx vercel
    npx vercel --prod

## Publicar en GitHub

Inicializa Git en esta carpeta y agrega la URL del repositorio que crees en GitHub:

    git init -b main
    git add .
    git commit -m "Crear sistema de turnos para clínica"
    git remote add origin https://github.com/USUARIO/clinica-turnos.git
    git push -u origin main

Después de conectar GitHub con Vercel, los siguientes cambios pueden desplegarse desde ese repositorio.
