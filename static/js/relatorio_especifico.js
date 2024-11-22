  // Manipular o envio do formulário
  document.getElementById('emailForm').addEventListener('submit', async function (event) {
    event.preventDefault(); // Evitar reload da página

    const dataInicial = document.getElementById('data_inicial').value;
    const dataFinal = document.getElementById('data_final').value;
    const email = document.getElementById('email').value;
    const code = document.getElementById('code_vsap').value;


    const responseMessage = document.getElementById('responseMessage');
    responseMessage.innerHTML = ''; // Limpar mensagens anteriores

    try {
        // Enviar requisição para a API
        const response = await fetch('http://26.154.23.230:8080/proxy/relatorio_especifico', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                data_inicial: dataInicial,
                data_final: dataFinal,
                email: email,
                codigo: code,
            }),
        });

        const result = await response.json();

        if (response.ok) {
            responseMessage.innerHTML = `<div class="alert alert-success">${result.message}</div>`;
        } else {
            responseMessage.innerHTML = `<div class="alert alert-danger">${result.error}</div>`;
        }
    } catch (error) {
        responseMessage.innerHTML = `<div class="alert alert-danger">Erro ao enviar a requisição: ${error.message}</div>`;
    }
});