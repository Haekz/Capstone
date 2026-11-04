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

    def test_sala_virtual_rechaza_admin_por_admin_id(self):
        """SCRUM-87: un administrador no entra a la sala virtual de una clase ajena."""
        self.client.force_login(self.u_admin)
        s = self.client.session
        s["admin_id"] = self.tutor.id_tutor
        s.save()

        resp = self.client.get(reverse("sala_virtual", args=[self.clase_aprobada.id_clase]))
        self.assertEqual(resp.status_code, 403)

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

    def _agregar_clases(self, profesor, cantidad, desde_hora=8):
        """`cantidad` clases de `profesor`, cada una con inscripcion, retiro y reporte."""
        for i in range(cantidad):
            c = Clase.objects.create(
                asignatura=self.asig,
                profesor=profesor,
                modalidad="online",
                horario=dt_time(desde_hora + i, 0),
            )
            Inscripcion.objects.create(alumno=self.alumno, clase=c, estado="confirmada")
            SolicitudRetiro.objects.create(
                profesor=profesor,
                monto=5000,
                banco=self.banco,
                tipo_cuenta="corriente",
                numero_cuenta="111",
            )
            Reporte.objects.create(remitente=self.u_alum, descripcion=f"Reporte {profesor.pk}-{i}")

    def _contar_consultas(self, usuario, sesion, nombre_url):
        self.client.force_login(usuario)
        s = self.client.session
        s.update(sesion)
        s.save()
        with CaptureQueriesContext(connection) as consultas:
            respuesta = self.client.get(reverse(nombre_url))
        self.assertEqual(respuesta.status_code, 200)
        return len(consultas), respuesta

    def test_orm_sin_n_mas_1_en_dashboards(self):
        """dashboard_admin y panel_profesor hacen las mismas consultas con pocos o muchos datos (O(1)).

        Comparar contra si mismo detecta cualquier N+1 sin depender de cuantos bloques tenga el panel.
        El techo absoluto atrapa recargas grandes; se midio 33 (admin) y 17 (profesor).
        """
        admin = (self.u_admin, {"admin_id": self.tutor.id_tutor}, "dashboard_admin")
        profe = (self.u_prof, {"profesor_id": self.prof_aprobado.id_profesor}, "panel_profesor")

        self._agregar_clases(self.prof_aprobado, 1)
        antes_adm, _ = self._contar_consultas(*admin)
        antes_prof, _ = self._contar_consultas(*profe)

        # Mas clases del mismo profesor y tres profesores nuevos con las suyas.
        self._agregar_clases(self.prof_aprobado, 4, desde_hora=14)
        for n in range(3):
            u = User.objects.create_user(
                username=f"3000000{n}-0", rut=f"3000000{n}-0", email=f"prof_extra{n}@lbwus.cl",
                password="PasswordSegura123!", rol="profesor", first_name=f"Extra{n}", genero=self.genero,
            )
            extra = Profesor.objects.create(user=u, especialidad=self.esp, titulo_estado=Profesor.TITULO_APROBADO)
            self._agregar_clases(extra, 2)

        despues_adm, _ = self._contar_consultas(*admin)
        despues_prof, r_prof = self._contar_consultas(*profe)

        self.assertEqual(despues_adm, antes_adm, "dashboard_admin crece con los datos (N+1)")
        self.assertEqual(despues_prof, antes_prof, "panel_profesor crece con los datos (N+1)")
        self.assertLessEqual(despues_adm, 36)
        self.assertLessEqual(despues_prof, 20)
        self.assertContains(r_prof, "Cálculo Vectorial")

    def test_formato_clp_y_alumnos_reg_dry(self):
        """Verifica utilidades DRY: formato_clp y delegación de alumnos_reg."""
        self.assertEqual(formato_clp(15000), "$15.000")
        self.assertEqual(formato_clp(0), "$0")
        resp = self.client.get(reverse("alumnos_reg"))
        self.assertEqual(resp.status_code, 200)
        self.assertIn("form", resp.context)
