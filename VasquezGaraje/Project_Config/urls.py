"""
URL configuration for VasquezGaraje MVC project.
"""
from django.contrib import admin
from django.urls import path
from Controllers import views

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', views.home, name='home'),
    path('login/', views.login, name='login'),
    path('logout/', views.logout, name='logout'),
    path('recuperar_contraseña/', views.recuperar_contraseña, name='recuperar_contraseña'),
    path('registro/', views.registro, name='registro'),
    path('inventario/', views.inventario, name='inventario'),
    path('admin_control/', views.admin_control, name='admin_control'),
    path('agendar_servicio/', views.agendar_servicio, name='agendar_servicio'),
    path('perfil/', views.perfil_usuario, name='ver_perfil'),
    path('perfil/editar/', views.editar_perfil, name='editar_perfil'),
    path('perfil/cambiar-contrasena/', views.cambiar_contrasena, name='cambiar_contrasena'),
    path('reserva/editar/<int:id>/', views.editar_reserva, name='editar_reserva'),
    path('reserva/cancelar/<int:id>/', views.cancelar_reserva, name='cancelar_reserva'),
    path('panel/perfil/', views.admin_perfil, name='admin_perfil'),
    path('panel/reservas/', views.admin_dashboard, name='admin_dashboard'),
    path('panel/inventario/', views.admin_inventario, name='admin_inventario'),
    path('panel/inventario/nuevo/', views.admin_insumo_nuevo, name='admin_insumo_nuevo'),
    path('panel/inventario/editar/<int:id>/', views.admin_insumo_editar, name='admin_insumo_editar'),
    path('panel/inventario/eliminar/<int:id>/', views.admin_insumo_eliminar, name='admin_insumo_eliminar'),
    path('panel/usuarios/', views.admin_usuarios, name='admin_usuarios'),
    path('panel/reservas/editar/<int:id>/', views.admin_editar_reserva, name='admin_editar_reserva'),
]
