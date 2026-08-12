"""Tests: Dienstplan (StaffShift CRUD + Tagesplan-Integration)."""
from datetime import date, timedelta

import pytest


class TestDienstplan:
    def test_schicht_anlegen_und_listen(self, client):
        r = client.post("/api/v1/staff-shifts", json={
            "employee_name": "Max Huber",
            "datum": date.today().isoformat(),
            "start_time": "08:00",
            "end_time": "16:00",
            "aufgabe": "Aussaat",
        })
        assert r.status_code == 201, r.text
        shift = r.json()
        assert shift["employee_name"] == "Max Huber"
        assert shift["start_time"] == "08:00"

        r = client.get("/api/v1/staff-shifts", params={
            "von_datum": date.today().isoformat(),
            "bis_datum": date.today().isoformat(),
        })
        assert r.status_code == 200
        assert len(r.json()) == 1

    def test_zeitraum_filter(self, client):
        client.post("/api/v1/staff-shifts", json={
            "employee_name": "Max", "datum": date.today().isoformat(),
        })
        r = client.get("/api/v1/staff-shifts", params={
            "von_datum": (date.today() + timedelta(days=1)).isoformat(),
        })
        assert r.json() == []

    def test_ungueltige_zeit_wird_abgelehnt(self, client):
        r = client.post("/api/v1/staff-shifts", json={
            "employee_name": "Max",
            "datum": date.today().isoformat(),
            "start_time": "25:99",
        })
        assert r.status_code == 422

    def test_update_und_delete(self, client):
        shift = client.post("/api/v1/staff-shifts", json={
            "employee_name": "Anna", "datum": date.today().isoformat(),
        }).json()

        r = client.patch(f"/api/v1/staff-shifts/{shift['id']}", json={"aufgabe": "Ernte"})
        assert r.status_code == 200
        assert r.json()["aufgabe"] == "Ernte"

        r = client.delete(f"/api/v1/staff-shifts/{shift['id']}")
        assert r.status_code == 204
        assert client.get("/api/v1/staff-shifts").json() == []

    def test_employee_vorschlaege(self, client):
        for name in ["Max Huber", "Anna Meier", "Max Huber"]:
            client.post("/api/v1/staff-shifts", json={
                "employee_name": name, "datum": date.today().isoformat(),
            })
        r = client.get("/api/v1/staff-shifts/employees")
        assert r.status_code == 200
        assert sorted(r.json()) == ["Anna Meier", "Max Huber"]

    def test_dienst_im_tagesplan(self, client):
        client.post("/api/v1/staff-shifts", json={
            "employee_name": "Max Huber",
            "datum": date.today().isoformat(),
            "start_time": "06:00",
            "end_time": "14:00",
            "aufgabe": "Ernte + Verpacken",
        })
        r = client.get("/api/v1/production/day-plan", params={"target_date": date.today().isoformat()})
        assert r.status_code == 200
        dienst = r.json()["dienst"]
        assert len(dienst) == 1
        assert dienst[0]["employee_name"] == "Max Huber"
        assert dienst[0]["aufgabe"] == "Ernte + Verpacken"
