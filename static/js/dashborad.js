// Função para tratar valores vazios ou nulos
function tratarValor(valor) {
    return valor || 'sem dados';
}
                                                                                            

// Função para carregar os dados do backend de forma assíncrona
async function loadData() {
    try {
        // Exibe o spinner de carregamento
        document.getElementById('spinner').style.display = 'flex';
        
        // Fazendo uma requisição para o servidor
        const response = await fetch('/api/dados');
        const data = await response.json(); // Espera um retorno em JSON

        // Referência para a tabela de Pendentes de Envio e seu corpo
        const pendentesTable = document.getElementById('pendentes-table');
        const pendentesTableBody = pendentesTable.getElementsByTagName('tbody')[0];

        // Verifica se há dados em Pendentes de Envio
        if (data.pendentes.length === 0) {
            // Se não houver dados, exibe a mensagem
            pendentesTable.style.display = 'none'; // Oculta a tabela
            const noDataMessage = document.createElement('p');
            noDataMessage.className = 'lead text-center text-muted';
            noDataMessage.innerText = 'Nenhum dado para ser enviado';
            pendentesTable.parentElement.appendChild(noDataMessage); // Adiciona a mensagem ao card
        } else {
            // Se houver dados, popula a tabela
            data.pendentes.forEach(row => {
                const tr = document.createElement('tr');
                tr.innerHTML = `
                    <td class="truncate" title="${tratarValor(row.nome_cliente)}">${tratarValor(row.nome_cliente)}</td>
                    <td>${tratarValor(row.Cod_escritorio)}</td>
                    <td>${tratarValor(row.Total)}</td>
                `;
                pendentesTableBody.appendChild(tr);
            });
        }

        // Preenchendo a tabela de Total Enviados Geral
        const totalEnviadosTable = document.getElementById('total-enviados-table').getElementsByTagName('tbody')[0];
        data.total_enviados.forEach(row => {
            const tr = document.createElement('tr');
            tr.innerHTML = `
                <td class="truncate" title="${tratarValor(row.nome_cliente)}">${tratarValor(row.nome_cliente)}</td>
                <td>${tratarValor(row.Codigo_VSAP)}</td>
                <td>${tratarValor(row.totalDistribuicoes)}</td>
            `;
            totalEnviadosTable.appendChild(tr);
        });

        // Preenchendo a tabela de Dados Detalhados
        const historicoTable = document.getElementById('historico-table').getElementsByTagName('tbody')[0];
        data.historico.forEach(row => {
            const tr = document.createElement('tr');
            tr.innerHTML = `
                <td>${tratarValor(row.cod_escritorio)}</td>
                <td class="truncate" title="${tratarValor(row.nome_cliente)}">${tratarValor(row.nome_cliente)}</td>
                <td>${tratarValor(row.localizador)}</td>
                <td>${tratarValor(row.origem)}</td>
                <td>${tratarValor(row.ultima_data_envio)}</td>
            `;
            historicoTable.appendChild(tr);
        });

        // Esconde o spinner e mostra o conteúdo
        document.getElementById('spinner').style.display = 'none';
        document.getElementById('content').style.display = 'block';
    } catch (error) {
        console.error('Erro ao carregar os dados:', error);
        document.getElementById('spinner').innerHTML = '<p>Erro ao carregar os dados.</p>';
    }
}

// Chama a função de carregamento de dados assim que a página é carregada
window.onload = loadData;
