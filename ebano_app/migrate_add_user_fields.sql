-- ---------------------------------------------------------
-- MIGRACIÓN: Añadir campos a la tabla usuarios
-- Agrega: nombre_completo, telefono, direccion
-- Crea índice único en correo (si no existe)
-- ---------------------------------------------------------

BEGIN;

-- Añadir columna nombre_completo (si no existe)
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name='usuarios' AND column_name='nombre_completo'
    ) THEN
        ALTER TABLE usuarios ADD COLUMN nombre_completo VARCHAR(150);
    END IF;
END$$;

-- Añadir columna telefono (si no existe)
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name='usuarios' AND column_name='telefono'
    ) THEN
        ALTER TABLE usuarios ADD COLUMN telefono VARCHAR(50);
    END IF;
END$$;

-- Añadir columna direccion (si no existe)
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name='usuarios' AND column_name='direccion'
    ) THEN
        ALTER TABLE usuarios ADD COLUMN direccion TEXT;
    END IF;
END$$;

-- Asegurar que 'correo' tenga índice único (en caso de que la tabla esté en un estado inconsistente)
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_indexes
        WHERE tablename = 'usuarios' AND indexname = 'usuarios_correo_key'
    ) THEN
        -- Si no existe una restricción UNIQUE sobre correo, intenta crearla.
        BEGIN
            ALTER TABLE usuarios ADD CONSTRAINT usuarios_correo_key UNIQUE (correo);
        EXCEPTION WHEN duplicate_object THEN
            -- Si falla porque ya existe (por nombre distinto), se ignora.
            RAISE NOTICE 'Constraint users_correo_key already exists or cannot be created.';
        END;
    END IF;
END$$;

COMMIT;
