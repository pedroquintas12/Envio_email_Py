from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Image
from reportlab.lib.units import cm
from reportlab.lib.enums import TA_CENTER
from io import BytesIO

def generate_pdf_in_memory(cliente, processos, localizador, data_do_dia, logo):
    # Cria um objeto BytesIO para armazenar o PDF em memória
    pdf_buffer = BytesIO()
    
    # Configurações do documento
    doc = SimpleDocTemplate(pdf_buffer, pagesize=A4)
    styles = getSampleStyleSheet()
    story = []

    title_style = ParagraphStyle(
        name='TitleStyle', 
        fontSize=18, 
        textColor=colors.darkblue, 
        alignment=TA_CENTER,  # Centralizar o texto
        spaceAfter=12,
        leading=22            
    )

    # Cabeçalho com logo
    if logo:
        logo_image = Image(logo, width=6*cm, height=3*cm)
        logo_image.hAlign = 'CENTER'
        story.append(logo_image)
        story.append(Spacer(1, 12))  

    # Título
    title = f"{cliente}"
    story.append(Paragraph(title, title_style))

    # Informações do relatório
    data_info = f"Data: {data_do_dia.strftime('%d/%m/%Y')}<br/>Localizador do Email: {localizador}<br/>Total de Processos: {len(processos)}"
    story.append(Paragraph(data_info, styles['Normal']))
    story.append(Spacer(1, 12))  

    # Laço para processos
    for idx, processo in enumerate(processos, start=1):
        # Título do processo
        distrib_text = f"<strong>Distribuição {idx} de {len(processos)}</strong>"
        story.append(Paragraph(distrib_text, styles['Heading2']))
        story.append(Spacer(1, 8))  # Espaçamento entre o título e os detalhes do processo

        # Detalhes do processo com espaçamento entre cada detalhe
        details = [
            f"<strong>Tribunal:</strong> {processo['tribunal']}",
            f"<strong>UF/Instância/Comarca:</strong> {processo['uf']}/{processo['instancia']}/{processo['comarca']}",
            f"<strong>Número do Processo:</strong> {processo['numero_processo']}",
            f"<strong>Data de Distribuição:</strong> {processo['data_distribuicao']}",
            f"<strong>Órgão:</strong> {processo['orgao']}",
            f"<strong>Classe Judicial:</strong> {processo['classe_judicial']}",
        ]

        for detail in details:
            story.append(Paragraph(detail, styles['Normal']))
            story.append(Spacer(1, 6))  # Adiciona espaçamento entre cada detalhe

        # Polo Ativo
        autores_exibidos = ', '.join([autor['nomeAutor'] for autor in processo['autor']])
        story.append(Paragraph(f"<strong>Polo Ativo:</strong> {autores_exibidos}<br/>", styles['Normal']))
        story.append(Spacer(1, 6))  # Espaçamento após o Polo Ativo

        # Polo Passivo
        reus_exibidos = ', '.join([reu['nomeReu'] for reu in processo['reu']])
        story.append(Paragraph(f"<strong>Polo Passivo:</strong> {reus_exibidos}<br/>", styles['Normal']))
        story.append(Spacer(1, 6))  # Espaçamento após o Polo Passivo

        # Links
        story.append(Paragraph("<strong>Links Relacionados:</strong>", styles['Normal']))
        for link_info in processo['links']:
            link_text = f"({link_info['tipoLink']}): {link_info['link_doc']}<br/>"
            story.append(Paragraph(link_text, styles['Normal']))
            story.append(Spacer(1, 12))  
        
        story.append(Spacer(1, 12))  # Espaçamento entre os processos

    # Construir o PDF
    doc.build(story)

    # Volta para o início do buffer para leitura
    pdf_buffer.seek(0)
    
    return pdf_buffer
