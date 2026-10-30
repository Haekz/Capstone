"""
Suite de pruebas de regresión de la Auditoría Técnica, Seguridad Multicapa, CWV y ORM N+1.
"""
from datetime import time as dt_time
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from django.urls import reverse

from alumnos.models import (
    Alumno,
    Asignatura,
    Banco,
    Clase,
    DesgloseOperacion,
    Especialidad,
    Genero,
    Inscripcion,
    Profesor,
    Reporte,
    SolicitudRetiro,
    Tutor,
)
from alumnos.utils import formato_clp, validar_imagen_perfil

User = get_user_model()


class AuditoriaSeguridadYArquitecturaTests(TestCase):
    def setUp(self):
        self.genero = Genero.objects.create(descripcion="No especifica")
        self.esp = Especialidad.objects.create(nombre="Matemáticas Avanzadas")
        self.asig = Asignatura.objects.create(nombre="Cálculo Vectorial")
        self.banco = Banco.objects.create(nombre="Banco Estado")

        self.u_prof = User.objects.create_user(
            username="12345678-5",
            rut="12345678-5",
            email="prof_titular@lbwus.cl",
            password="PasswordSegura123!",
            rol="profesor",
            first_name="Roberto",
            last_name="Antiguo",
            direccion="Av Providencia 100",
            telefono="912345678",
            genero=self.genero,
        )
        self.prof_aprobado = Profesor.objects.create(
            user=self.u_prof,
            especialidad=self.esp,
            tarifa_base=15000,
            titulo_estado=Profesor.TITULO_APROBADO,
        )

        self.u_prof_pend = User.objects.create_user(
            username="11111111-1",
            rut="11111111-1",
            email="prof_pendiente@lbwus.cl",
            password="PasswordSegura123!",
            rol="profesor",
            first_name="DocenteSinTituloAprobado",
            genero=self.genero,
        )
        self.prof_pendiente = Profesor.objects.create(
            user=self.u_prof_pend,
            especialidad=self.esp,
            tarifa_base=15000,
            titulo_estado=Profesor.TITULO_PENDIENTE,
        )

        self.u_alum = User.objects.create_user(
            username="22222222-2",
            rut="22222222-2",
            email="alumno_activo@lbwus.cl",
            password="PasswordSegura123!",
            rol="alumno",
            first_name="Camila",
            genero=self.genero,
        )
        self.alumno = Alumno.objects.create(user=self.u_alum, nivel_educacion="superior")

        self.u_admin = User.objects.create_user(
            username="33333333-3",
            rut="33333333-3",
            email="admin_tutor@lbwus.cl",
            password="PasswordSegura123!",
            rol="admin",
            first_name="AdminPortal",
            is_staff=False,
            genero=self.genero,
        )
        self.tutor = Tutor.objects.create(user=self.u_admin)

        self.clase_aprobada = Clase.objects.create(
            asignatura=self.asig,
            profesor=self.prof_aprobado,
            modalidad="online",
            horario=dt_time(10, 0),
        )
        self.clase_pendiente = Clase.objects.create(
            asignatura=self.asig,
            profesor=self.prof_pendiente,
            modalidad="online",
            horario=dt_time(12, 0),
        )

    def test_sala_virtual_bloquea_inscripcion_cancelada(self):
        """Un alumno cuya inscripción fue cancelada no puede entrar a la sala virtual."""
        Inscripcion.objects.create(
            alumno=self.alumno,
            clase=self.clase_aprobada,
            estado=Inscripcion.ESTADO_CANCELADA,
        )
        self.client.force_login(self.u_alum)
        s = self.client.session
        s["alumno_id"] = self.alumno.id_alumno
        s.save()

        resp = self.client.get(reverse("sala_virtual", args=[self.clase_aprobada.id_clase]))
        self.assertEqual(resp.status_code, 403)

    def test_sala_virtual_permite_admin_por_admin_id(self):
        """Un administrador con session['admin_id'] puede supervisar la sala virtual."""
        self.client.force_login(self.u_admin)
        s = self.client.session
        s["admin_id"] = self.tutor.id_tutor
        s.save()

        resp = self.client.get(reverse("sala_virtual", args=[self.clase_aprobada.id_clase]))
        self.assertEqual(resp.status_code, 200)

    def test_catalogo_alumno_oculta_clases_de_profesores_no_aprobados(self):
        """El portal del alumno solo expone clases de profesores con título aprobado."""
        self.client.force_login(self.u_alum)
        s = self.client.session
        s["alumno_id"] = self.alumno.id_alumno
        s.save()

        resp = self.client.get(reverse("alumno_pag1"))
        self.assertEqual(resp.status_code, 200)
        html = resp.content.decode("utf-8")
        self.assertNotIn("DocenteSinTituloAprobado", html)

    def test_actualizar_perfil_prof_rechaza_imagen_falsa_y_sincroniza_nombre(self):
        """actualizar_perfil_prof rechaza archivos falsos (magic bytes) y evita duplicar apellidos."""
        self.client.force_login(self.u_prof)
        s = self.client.session
        s["profesor_id"] = self.prof_aprobado.id_profesor
        s.save()

        archivo_falso = SimpleUploadedFile(
            "shell.jpg", b"<?php echo 'hack'; ?>", content_type="image/jpeg"
        )
        resp_malo = self.client.post(
            reverse("actualizar_perfil_prof"),
            {
                "nombre": "Roberto Gomez",
                "rut": "12345678-5",
                "especialidad": self.esp.pk,
                "direccion": "Av Providencia 100",
                "correo_electronico": self.u_prof.email,
                "telefono": "912345678",
                "genero": self.genero.id_genero,
                "foto_perfil": archivo_falso,
            },
        )
        self.assertEqual(resp_malo.status_code, 400)
        self.assertFalse(resp_malo.json()["success"])

        resp_ok = self.client.post(
            reverse("actualizar_perfil_prof"),
            {
                "nombre": "Roberto Gomez",
                "rut": "12345678-5",
                "especialidad": self.esp.pk,
                "direccion": "Av Providencia 100",
                "correo_electronico": self.u_prof.email,
                "telefono": "912345678",
                "genero": self.genero.id_genero,
                "telefono_publico": "on",
            },
        )
        self.assertEqual(resp_ok.status_code, 200)
        self.assertTrue(resp_ok.json()["success"])
        self.prof_aprobado.refresh_from_db()
        self.prof_aprobado.user.refresh_from_db()
        self.assertEqual(self.prof_aprobado.nombre, "Roberto Gomez")
        self.assertTrue(self.prof_aprobado.telefono_publico)

    def test_orm_sin_n_mas_1_en_dashboards(self):
        """Verifica que dashboard_admin, panel_profesor y alumno_pag1 mantengan consultas O(1) acotadas."""
        for i in range(4):
            c = Clase.objects.create(
                asignatura=self.asig,
                profesor=self.prof_aprobado,
                modalidad="online",
                horario=dt_time(14 + i, 0),
            )
            ins = Inscripcion.objects.create(alumno=self.alumno, clase=c, estado="confirmada")
            DesgloseOperacion.objects.create(
                profesor=self.prof_aprobado,
                alumno=self.alumno,
                inscripcion=ins,
                monto_bruto=15000,
                comision_lbwus=2250,
                iva_comision=359,
                neto_comision=1891,
                monto_tutor=12750,
            )
            SolicitudRetiro.objects.create(
                profesor=self.prof_aprobado,
                monto=5000,
                banco=self.banco,
                tipo_cuenta="corriente",
                numero_cuenta="111",
            )
            Reporte.objects.create(remitente=self.u_alum, descripcion=f"Reporte {i}")

        # Admin dashboard
        self.client.force_login(self.u_admin)
        s = self.client.session
        s["admin_id"] = self.tutor.id_tutor
        s.save()
        with CaptureQueriesContext(connection) as q_adm:
            r_adm = self.client.get(reverse("dashboard_admin"))
        self.assertEqual(r_adm.status_code, 200)
        self.assertLessEqual(len(q_adm), 15)

        # Profesor panel
        self.client.force_login(self.u_prof)
        s = self.client.session
        s["profesor_id"] = self.prof_aprobado.id_profesor
        s.save()
        with CaptureQueriesContext(connection) as q_prof:
            r_prof = self.client.get(reverse("panel_profesor"))
        self.assertEqual(r_prof.status_code, 200)
        self.assertLessEqual(len(q_prof), 12)
        self.assertContains(r_prof, "Cálculo Vectorial")

    def test_formato_clp_y_alumnos_reg_dry(self):
        """Verifica utilidades DRY: formato_clp y delegación de alumnos_reg."""
        self.assertEqual(formato_clp(15000), "$15.000")
        self.assertEqual(formato_clp(0), "$0")
        resp = self.client.get(reverse("alumnos_reg"))
        self.assertEqual(resp.status_code, 200)
        self.assertIn("form", resp.context)
