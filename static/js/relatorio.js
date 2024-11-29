document.addEventListener('DOMContentLoaded', function () {
    // Manipular o envio do formulário
    document.getElementById('emailForm').addEventListener('submit', async function (event) {
        event.preventDefault(); // Evitar reload da página

        const dataInicial = document.getElementById('data_inicial').value;
        const dataFinal = document.getElementById('data_final').value;
        const email = document.getElementById('email').value;
        const submitBtn = document.getElementById('submitBtn');

        // Alterar o estado do botão para mostrar o carregando
        submitBtn.disabled = true;
        submitBtn.innerHTML = 'Enviando... <span class="spinner-border spinner-border-sm" role="status" aria-hidden="true"></span>';

        try {
            // Enviar requisição para a API
            const response = await fetch('http://26.154.23.230:8080/proxy/relatorio', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    data_inicial: dataInicial,
                    data_final: dataFinal,
                    email: email,
                }),
            });

            const result = await response.json();

            // Reverter o estado do botão para seu estado normal
            submitBtn.disabled = false;
            submitBtn.innerHTML = 'Enviar';

            if (response.ok) {
                // Exibir notificação de sucesso
                Swal.fire({
                    icon: 'success',
                    title: 'Relatório Enviado!',
                    text: result.message,
                    timer: 5000,
                    timerProgressBar: true,
                });

                // Exibir o total de publicações enviadas
                Swal.fire({
                    icon: 'success',
                    title: 'Sucesso!',
                    text: `Publicações enviadas: ${result.total_processos}`,
                    showConfirmButton: false,
                    timer: 3000,
                    position: 'top-end',
                    toast: true,
                    background: '#28a745',
                });
            } else {
                // Se a resposta não for ok, exibe erro com a mensagem da API
                Swal.fire({
                    icon: 'error',
                    title: 'Erro!',
                    text: result.error || 'Erro desconhecido da API',
                    showConfirmButton: false,
                    timer: 3000,
                    position: 'top-end',
                    toast: true,
                    background: '#dc3545',  // Cor de fundo vermelha
                    color: '#ffffff',  // Cor do texto para contraste (opcional)
                });
            }
        } catch (error) {
            // Reverter o estado do botão e mostrar erro
            submitBtn.disabled = false;
            submitBtn.innerHTML = 'Enviar';

            // Exibir notificação para erros no JavaScript ou conexão
            Swal.fire({
                icon: 'error',
                title: 'Erro!',
                text: `Erro ao enviar a requisição: ${error.message}`,
            });
        }
    });
});
