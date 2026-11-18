async function fetchWithAuth(url, options = {}) {
    let response = await fetch(url, options);
    if (response.status === 401 || response.status === 422) {
        const refreshResponse = await fetch('/refresh', { method: 'POST' });
        console.log(refreshResponse.status);
        if (refreshResponse.status !== 401) {
            response = await fetch(url, options); // повторяем запрос
        } else {
            window.location.href = '/'; // refresh тоже истёк
        }
    }
    return response;
}

async function loadLots() {
    const response = await fetchWithAuth('/lots');
    const data = await response.json();
    const container = document.getElementById('lots');
    container.innerHTML = '';

    if (!data.lots || data.lots.length === 0) {
        container.innerHTML = '<div class="empty">Лотов пока нет ¯\\_(ツ)_/¯</div>';
        return;
    }

    data.lots.forEach(lot => {
        container.innerHTML += `
            <div class="frame">
                <div class="lot">
                    <h3>${lot.title}</h3>
                    <div class="price">Текущая ставка: ${lot.current_price} ₽</div>
                    <div class="time">До конца: ${lot.ends_at}</div>
                    <div class="meta">Лидер: ${lot.leader || 'нет'}</div>
                    <div class="meta">Контакты: ${lot.contact}</div>
                    ${lot.is_owner ? `<button onclick="deleteLot(${lot.id})" style="background-color: #f44336; color: white;">Удалить лот</button>` : `
                    <div class="bid-form">
                        <input type="number" id="bid-${lot.id}" placeholder="Ваша ставка">
                        <button onclick="placeBid(${lot.id})">Сделать ставку</button>
                    </div>`}
                </div>
            </div>
            <p></p>
        `;
    });
}

async function createLot() {
    const title = document.getElementById('lotTitle').value;
    const price = document.getElementById('lotPrice').value;
    const endsAt = document.getElementById('lotEndsAt').value;
    const contact= document.getElementById('contact').value;

    if (!title || !price || !endsAt) {
        alert('Заполните все поля');
        return;
    }

    await fetchWithAuth('/lots', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ 'title':title, 'price':price, 'ends_at': endsAt, 'contact':contact})
    });

    document.getElementById('lotTitle').value = '';
    document.getElementById('lotPrice').value = '';
    document.getElementById('lotEndsAt').value = '';
    loadLots();
}

async function placeBid(lotId) {
    const input = document.getElementById(`bid-${lotId}`);
    const amount = input.value;

    if (!amount) {
        alert('Введите сумму');
        return;
    }

    const response = await fetchWithAuth(`/lots/${lotId}/bid`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ 'amount': Number(amount) })
    });

    if (response.ok) {
        input.value = '';
        loadLots();
    } else {
        const error = await response.json();
        alert(error.detail || 'Ошибка');
    }
}


async function loadMessages() {
            const response = await fetchWithAuth('/messages');
            const data = await response.json();
            const container = document.getElementById('messages');
            container.innerHTML = '';

            if (!data.messages || data.messages.length === 0) {
                container.innerHTML = '<div class="empty">Сообщений пока нет ¯\\_(ツ)_/¯</div>';
                return;
            }

            data.messages.forEach(msg => {
                const statusClass = `status-${msg.status}`;
                container.innerHTML += `
                    <div class="frame">
                        <div class="message">
                            <div class="text">${msg.text}</div>
                            <div class="meta">${msg.created_at}</div>
                            <div class="status ${statusClass}">Статус: ${msg.status}</div>
                        </div>
                    </div>
                    <p></p>
                `;
            });
        }

async function deleteLot(lotId) {
    if (!confirm('Удалить лот?')) return;

    const response = await fetchWithAuth(`/lots/${lotId}`, {
        method: 'DELETE'
    });

    if (response.ok) {
        loadLots();
    } else {
        const error = await response.json();
        alert(error.detail || 'Ошибка');
    }
}


async function winloadLots() {
    const response = await fetchWithAuth('/winlots');
    const data = await response.json();
    const container = document.getElementById('lots');
    container.innerHTML = '';

    if (!data.lots || data.lots.length === 0) {
        container.innerHTML = '<div class="empty">Лотов пока нет ¯\\_(ツ)_/¯</div>';
        return;
    }

    data.lots.forEach(lot => {
        container.innerHTML += `
            <div class="frame">
                <div class="lot">
                    <h3>${lot.title}</h3>
                    <div class="meta">Контакты: ${lot.contact}</div>
                </div>
            </div>
            <p></p>
        `;
    });
}