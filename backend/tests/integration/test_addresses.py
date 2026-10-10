from tests.conftest import signup

ADDR = {
    "full_name": "Ada Lovelace",
    "phone": "+919876543210",
    "line1": "12 MG Road",
    "city": "Bengaluru",
    "state": "Karnataka",
    "postal_code": "560001",
}


async def test_address_crud_and_defaults(client, customer):
    url = "/api/v1/users/me/addresses"
    first = (await client.post(url, json=ADDR, headers=customer)).json()
    assert first["is_default_shipping"] and first["is_default_billing"]  # first address auto-default

    second = (
        await client.post(url, json={**ADDR, "line1": "2nd", "is_default_shipping": True}, headers=customer)
    ).json()
    rows = {a["id"]: a for a in (await client.get(url, headers=customer)).json()}
    assert rows[second["id"]]["is_default_shipping"] and not rows[first["id"]]["is_default_shipping"]
    assert rows[first["id"]]["is_default_billing"]

    r = await client.put(f"{url}/{first['id']}", json={**ADDR, "city": "Mysuru"}, headers=customer)
    assert r.json()["city"] == "Mysuru" and r.json()["is_default_billing"]  # can't un-default by omission

    assert (await client.delete(f"{url}/{second['id']}", headers=customer)).status_code == 204
    remaining = (await client.get(url, headers=customer)).json()
    assert len(remaining) == 1 and remaining[0]["is_default_shipping"]  # default promoted


async def test_address_validation(client, customer):
    r = await client.post(
        "/api/v1/users/me/addresses", json={**ADDR, "postal_code": "12345"}, headers=customer
    )
    assert r.status_code == 422
    r = await client.post(
        "/api/v1/users/me/addresses", json={**ADDR, "country": "us", "postal_code": "94107"}, headers=customer
    )
    assert r.status_code == 201 and r.json()["country"] == "US"


async def test_cannot_touch_someone_elses_address(client, customer):
    addr = (await client.post("/api/v1/users/me/addresses", json=ADDR, headers=customer)).json()
    other = await signup(client, "other@example.com")
    url = f"/api/v1/users/me/addresses/{addr['id']}"
    assert (await client.put(url, json=ADDR, headers=other)).status_code == 404
    assert (await client.delete(url, headers=other)).status_code == 404
