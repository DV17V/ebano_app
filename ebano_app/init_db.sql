-- ---------------------------------------------------------
-- PROYECTO ÉBANO - FASE 1
-- Estructura base de datos PostgreSQL
-- Autor: Diego A. Villota
-- ---------------------------------------------------------

-- Si existe una versión anterior, se eliminan las tablas en orden correcto
DROP TABLE IF EXISTS detalle_pedidos CASCADE;
DROP TABLE IF EXISTS pedidos CASCADE;
DROP TABLE IF EXISTS productos CASCADE;
DROP TABLE IF EXISTS usuarios CASCADE;
DROP TABLE IF EXISTS reseñas CASCADE;

-- ---------------------------------------------------------
-- TABLA: usuarios
-- ---------------------------------------------------------
CREATE TABLE usuarios (
    id SERIAL PRIMARY KEY,
    nombre_usuario VARCHAR(50) UNIQUE NOT NULL,
    correo VARCHAR(100) UNIQUE NOT NULL,
    contraseña VARCHAR(255) NOT NULL,
    rol VARCHAR(20) NOT NULL DEFAULT 'cliente',
    fecha_registro TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ---------------------------------------------------------
-- TABLA: productos
-- ---------------------------------------------------------
CREATE TABLE productos (
    id SERIAL PRIMARY KEY,
    nombre VARCHAR(100) NOT NULL,
    descripcion TEXT,
    precio NUMERIC(10,2) NOT NULL,
    stock INT DEFAULT 0,
    imagen_url VARCHAR(255),
    fecha_creacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ---------------------------------------------------------
-- TABLA: pedidos
-- ---------------------------------------------------------
CREATE TABLE pedidos (
    id SERIAL PRIMARY KEY,
    id_usuario INT REFERENCES usuarios(id) ON DELETE CASCADE,
    fecha_pedido TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    estado VARCHAR(20) DEFAULT 'pendiente',
    total NUMERIC(10,2) DEFAULT 0
);

-- ---------------------------------------------------------
-- TABLA: detalle_pedidos
-- ---------------------------------------------------------
CREATE TABLE detalle_pedidos (
    id SERIAL PRIMARY KEY,
    id_pedido INT REFERENCES pedidos(id) ON DELETE CASCADE,
    id_producto INT REFERENCES productos(id) ON DELETE CASCADE,
    cantidad INT DEFAULT 1,
    subtotal NUMERIC(10,2) DEFAULT 0
);

-- ---------------------------------------------------------
-- TABLA: reseñas
-- ---------------------------------------------------------
CREATE TABLE reseñas (
    id SERIAL PRIMARY KEY,
    id_usuario INT REFERENCES usuarios(id) ON DELETE CASCADE,
    id_producto INT REFERENCES productos(id) ON DELETE CASCADE,
    comentario TEXT,
    calificacion INT CHECK (calificacion BETWEEN 1 AND 5),
    fecha TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ---------------------------------------------------------
-- INSERCIÓN DE DATOS DE PRUEBA
-- ---------------------------------------------------------

INSERT INTO usuarios (nombre_usuario, correo, contraseña, rol)
VALUES
('admin', 'admin@ebano.com', 'admin1234', 'admin'),
('cliente1', 'cliente1@correo.com', 'pass1', 'cliente'),
('cliente2', 'cliente2@correo.com', 'pass2', 'cliente');

INSERT INTO productos (nombre, descripcion, precio, stock, imagen_url)
VALUES
('Ébano Clásico 250ml', 'Vino artesanal sin alcohol con notas de frutos rojos.', 25000, 50, 'img/ebano_clasico_250.jpg'),
('Ébano Dorado 500ml', 'Variante dorada con matices cítricos, edición limitada.', 42000, 30, 'img/ebanodorado500.jpg'),
('Ébano Reserva 750ml', 'Vino sin alcohol con fermentación natural de uva borgoña.', 60000, 20, 'img/ebano_reserva_750.jpg');

-- Simulación de pedidos
INSERT INTO pedidos (id_usuario, estado, total)
VALUES (2, 'entregado', 85000), (3, 'pendiente', 42000);

INSERT INTO detalle_pedidos (id_pedido, id_producto, cantidad, subtotal)
VALUES 
(1, 1, 2, 50000),
(1, 3, 1, 60000),
(2, 2, 1, 42000);

INSERT INTO reseñas (id_usuario, id_producto, comentario, calificacion)
VALUES 
(2, 1, 'Excelente sabor, ideal para cenas.', 5),
(3, 2, 'Muy refrescante, aunque un poco dulce.', 4);

-- ---------------------------------------------------------
-- SCRIPT DE CARRITO DE COMPRAS
-- ---------------------------------------------------------

-- Tabla de pedidos
CREATE TABLE IF NOT EXISTS pedidos (
    id SERIAL PRIMARY KEY,
    id_usuario INTEGER NOT NULL REFERENCES usuarios(id),
    fecha TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    total NUMERIC(10, 2),
    estado VARCHAR(20) DEFAULT 'pendiente'
);

-- Detalle de cada pedido
CREATE TABLE IF NOT EXISTS detalle_pedido (
    id SERIAL PRIMARY KEY,
    id_pedido INTEGER REFERENCES pedidos(id) ON DELETE CASCADE,
    id_producto INTEGER REFERENCES productos(id),
    cantidad INTEGER DEFAULT 1,
    subtotal NUMERIC(10, 2)
);

-- ---------------------------------------------------------
-- FIN DEL SCRIPT
-- ---------------------------------------------------------
