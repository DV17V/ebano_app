--
-- PostgreSQL database dump
--

\restrict Qml3AZhdnYhAlzOeCGy4bieAWEfi4gE0jv2WoDyRYCZmnBieejEw7DwJDlijEAC

-- Dumped from database version 17.7
-- Dumped by pg_dump version 17.7

SET statement_timeout = 0;
SET lock_timeout = 0;
SET idle_in_transaction_session_timeout = 0;
SET transaction_timeout = 0;
SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;
SELECT pg_catalog.set_config('search_path', '', false);
SET check_function_bodies = false;
SET xmloption = content;
SET client_min_messages = warning;
SET row_security = off;

SET default_tablespace = '';

SET default_table_access_method = heap;

--
-- Name: detalle_pedidos; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.detalle_pedidos (
    id integer NOT NULL,
    id_pedido integer,
    id_producto integer,
    cantidad integer DEFAULT 1,
    subtotal numeric(10,2) DEFAULT 0
);


ALTER TABLE public.detalle_pedidos OWNER TO postgres;

--
-- Name: detalle_pedidos_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.detalle_pedidos_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.detalle_pedidos_id_seq OWNER TO postgres;

--
-- Name: detalle_pedidos_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.detalle_pedidos_id_seq OWNED BY public.detalle_pedidos.id;


--
-- Name: pedidos; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.pedidos (
    id integer NOT NULL,
    id_usuario integer,
    fecha_pedido timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    estado character varying(20) DEFAULT 'pendiente'::character varying,
    total numeric(10,2) DEFAULT 0
);


ALTER TABLE public.pedidos OWNER TO postgres;

--
-- Name: pedidos_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.pedidos_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.pedidos_id_seq OWNER TO postgres;

--
-- Name: pedidos_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.pedidos_id_seq OWNED BY public.pedidos.id;


--
-- Name: productos; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.productos (
    id integer NOT NULL,
    nombre character varying(100) NOT NULL,
    descripcion text,
    precio numeric(10,2) NOT NULL,
    stock integer DEFAULT 0,
    imagen_url character varying(255),
    fecha_creacion timestamp without time zone DEFAULT CURRENT_TIMESTAMP
);


ALTER TABLE public.productos OWNER TO postgres;

--
-- Name: productos_backup_pre_precios; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.productos_backup_pre_precios (
    id integer,
    nombre character varying(100),
    descripcion text,
    precio numeric(10,2),
    stock integer,
    imagen_url character varying(255),
    fecha_creacion timestamp without time zone
);


ALTER TABLE public.productos_backup_pre_precios OWNER TO postgres;

--
-- Name: productos_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.productos_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.productos_id_seq OWNER TO postgres;

--
-- Name: productos_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.productos_id_seq OWNED BY public.productos.id;


--
-- Name: resenas; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.resenas (
    id integer NOT NULL,
    id_usuario integer,
    id_producto integer,
    comentario text,
    calificacion integer,
    fecha timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT "reseñas_calificacion_check" CHECK (((calificacion >= 1) AND (calificacion <= 5)))
);


ALTER TABLE public.resenas OWNER TO postgres;

--
-- Name: reseñas_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public."reseñas_id_seq"
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public."reseñas_id_seq" OWNER TO postgres;

--
-- Name: reseñas_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public."reseñas_id_seq" OWNED BY public.resenas.id;


--
-- Name: usuarios; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.usuarios (
    id integer NOT NULL,
    nombre_usuario character varying(50) NOT NULL,
    correo character varying(100) NOT NULL,
    "contraseña" character varying(255) NOT NULL,
    rol character varying(20) DEFAULT 'cliente'::character varying NOT NULL,
    fecha_registro timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    nombre_completo character varying(150),
    telefono character varying(50),
    direccion text,
    estado character varying(50),
    pais character varying(50) DEFAULT 'Estados Unidos'::character varying
);


ALTER TABLE public.usuarios OWNER TO postgres;

--
-- Name: usuarios_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.usuarios_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.usuarios_id_seq OWNER TO postgres;

--
-- Name: usuarios_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.usuarios_id_seq OWNED BY public.usuarios.id;


--
-- Name: detalle_pedidos id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.detalle_pedidos ALTER COLUMN id SET DEFAULT nextval('public.detalle_pedidos_id_seq'::regclass);


--
-- Name: pedidos id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.pedidos ALTER COLUMN id SET DEFAULT nextval('public.pedidos_id_seq'::regclass);


--
-- Name: productos id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.productos ALTER COLUMN id SET DEFAULT nextval('public.productos_id_seq'::regclass);


--
-- Name: resenas id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.resenas ALTER COLUMN id SET DEFAULT nextval('public."reseñas_id_seq"'::regclass);


--
-- Name: usuarios id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.usuarios ALTER COLUMN id SET DEFAULT nextval('public.usuarios_id_seq'::regclass);


--
-- Data for Name: detalle_pedidos; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY public.detalle_pedidos (id, id_pedido, id_producto, cantidad, subtotal) FROM stdin;
1	1	1	2	50000.00
2	1	3	1	60000.00
3	2	2	1	42000.00
4	4	2	3	126.00
5	5	2	1	42000.00
6	6	2	2	84000.00
\.


--
-- Data for Name: pedidos; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY public.pedidos (id, id_usuario, fecha_pedido, estado, total) FROM stdin;
4	7	2025-11-14 16:09:39.86931	Pendiente	126.00
1	2	2025-10-12 23:07:21.442412	Entregado	85000.00
2	3	2025-10-12 23:07:21.442412	Entregado	42000.00
5	7	2025-11-14 21:26:21.956459	Entregado	42000.00
6	7	2025-11-15 00:15:46.327747	Pendiente	84000.00
\.


--
-- Data for Name: productos; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY public.productos (id, nombre, descripcion, precio, stock, imagen_url, fecha_creacion) FROM stdin;
3	Ébano Reserva 750ml	Vino sin alcohol con fermentación natural de uva borgoña.	50000.00	20	img/ebano_reserva_750.jpg	2025-10-12 23:07:21.442412
1	Ébano Clásico 250ml	Vino artesanal sin alcohol con notas de frutos rojos.	25000.00	30	img/ebano_clasico_250.jpg	2025-10-12 23:07:21.442412
2	Ébano Dorado 500ml	Variante dorada con matices cítricos, edición limitada.	45000.00	3	img/ebanodorado500.jpg	2025-10-12 23:07:21.442412
\.


--
-- Data for Name: productos_backup_pre_precios; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY public.productos_backup_pre_precios (id, nombre, descripcion, precio, stock, imagen_url, fecha_creacion) FROM stdin;
1	Ébano Clásico 250ml	Vino artesanal sin alcohol con notas de frutos rojos.	25.00	50	img/ebano_clasico_250.jpg	2025-10-12 23:07:21.442412
3	Ébano Reserva 750ml	Vino sin alcohol con fermentación natural de uva borgoña.	60.00	20	img/ebano_reserva_750.jpg	2025-10-12 23:07:21.442412
2	Ébano Dorado 500ml	Variante dorada con matices cítricos, edición limitada.	42.00	30	img/ebanodorado500.jpg	2025-10-12 23:07:21.442412
\.


--
-- Data for Name: resenas; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY public.resenas (id, id_usuario, id_producto, comentario, calificacion, fecha) FROM stdin;
1	2	1	Excelente sabor, ideal para cenas.	5	2025-10-12 23:07:21.442412
2	3	2	Muy refrescante, aunque un poco dulce.	4	2025-10-12 23:07:21.442412
4	7	2	Buen sabor, calidad superior. Muy recomendado	5	2025-11-14 21:47:22.446658
\.


--
-- Data for Name: usuarios; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY public.usuarios (id, nombre_usuario, correo, "contraseña", rol, fecha_registro, nombre_completo, telefono, direccion, estado, pais) FROM stdin;
1	admin	admin@ebano.com	admin1234	admin	2025-10-12 23:07:21.442412	\N	\N	\N	\N	Estados Unidos
6	diegoandresvillota23	diegoandresvillota23@gmail.com	$2b$12$S6iC5xmN5GZs9oP3f5Y6qOJ3LvBdd5TILiFC8W0qGRdinJb8mfyeO	admin	2025-10-13 00:46:19.756997	Diego Andres Villota	3108965286	Ipiales-Nariño	\N	Estados Unidos
8	ituyan	ituyan@gmail.com	$2b$12$gvlDSe38NZK0j9gbh6oyAeKra1ymoPAT2SiBG4cYtGz.kgmPaXWeO	admin	2025-10-15 11:52:56.748619	Brayan Estiven Ceron	3162727282	Ipiales-Nariño	\N	Estados Unidos
2	cliente1	cliente1@correo.com	pass1	cliente	2025-10-12 23:07:21.442412	\N	\N	\N	New York	Estados Unidos
3	cliente2	cliente2@correo.com	pass2	cliente	2025-10-12 23:07:21.442412	\N	\N	\N	Florida	Estados Unidos
7	duvan	duvan@gmail.com	$2b$12$ng2PgHkZSL0tHFC1wAaw0uqJTKbekdvyObVDyZu.TD6ntDSGUe8SG	cliente	2025-10-13 00:56:41.276356	Duvan Esteban Cultid	3108627262	Ipiales-Nariño	Georgia	Estados Unidos
\.


--
-- Name: detalle_pedidos_id_seq; Type: SEQUENCE SET; Schema: public; Owner: postgres
--

SELECT pg_catalog.setval('public.detalle_pedidos_id_seq', 6, true);


--
-- Name: pedidos_id_seq; Type: SEQUENCE SET; Schema: public; Owner: postgres
--

SELECT pg_catalog.setval('public.pedidos_id_seq', 6, true);


--
-- Name: productos_id_seq; Type: SEQUENCE SET; Schema: public; Owner: postgres
--

SELECT pg_catalog.setval('public.productos_id_seq', 3, true);


--
-- Name: reseñas_id_seq; Type: SEQUENCE SET; Schema: public; Owner: postgres
--

SELECT pg_catalog.setval('public."reseñas_id_seq"', 4, true);


--
-- Name: usuarios_id_seq; Type: SEQUENCE SET; Schema: public; Owner: postgres
--

SELECT pg_catalog.setval('public.usuarios_id_seq', 8, true);


--
-- Name: detalle_pedidos detalle_pedidos_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.detalle_pedidos
    ADD CONSTRAINT detalle_pedidos_pkey PRIMARY KEY (id);


--
-- Name: pedidos pedidos_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.pedidos
    ADD CONSTRAINT pedidos_pkey PRIMARY KEY (id);


--
-- Name: productos productos_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.productos
    ADD CONSTRAINT productos_pkey PRIMARY KEY (id);


--
-- Name: resenas reseñas_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.resenas
    ADD CONSTRAINT "reseñas_pkey" PRIMARY KEY (id);


--
-- Name: usuarios usuarios_correo_key; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.usuarios
    ADD CONSTRAINT usuarios_correo_key UNIQUE (correo);


--
-- Name: usuarios usuarios_nombre_usuario_key; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.usuarios
    ADD CONSTRAINT usuarios_nombre_usuario_key UNIQUE (nombre_usuario);


--
-- Name: usuarios usuarios_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.usuarios
    ADD CONSTRAINT usuarios_pkey PRIMARY KEY (id);


--
-- Name: detalle_pedidos detalle_pedidos_id_pedido_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.detalle_pedidos
    ADD CONSTRAINT detalle_pedidos_id_pedido_fkey FOREIGN KEY (id_pedido) REFERENCES public.pedidos(id) ON DELETE CASCADE;


--
-- Name: detalle_pedidos detalle_pedidos_id_producto_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.detalle_pedidos
    ADD CONSTRAINT detalle_pedidos_id_producto_fkey FOREIGN KEY (id_producto) REFERENCES public.productos(id) ON DELETE CASCADE;


--
-- Name: pedidos pedidos_id_usuario_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.pedidos
    ADD CONSTRAINT pedidos_id_usuario_fkey FOREIGN KEY (id_usuario) REFERENCES public.usuarios(id) ON DELETE CASCADE;


--
-- Name: resenas reseñas_id_producto_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.resenas
    ADD CONSTRAINT "reseñas_id_producto_fkey" FOREIGN KEY (id_producto) REFERENCES public.productos(id) ON DELETE CASCADE;


--
-- Name: resenas reseñas_id_usuario_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.resenas
    ADD CONSTRAINT "reseñas_id_usuario_fkey" FOREIGN KEY (id_usuario) REFERENCES public.usuarios(id) ON DELETE CASCADE;


--
-- PostgreSQL database dump complete
--

\unrestrict Qml3AZhdnYhAlzOeCGy4bieAWEfi4gE0jv2WoDyRYCZmnBieejEw7DwJDlijEAC

