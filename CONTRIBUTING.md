# Guia de Contribuição

Obrigado por considerar contribuir para o LangGraph MCP! Aqui estão algumas diretrizes para ajudar no processo de contribuição.

## Como Contribuir

1. **Relate problemas**
   - Verifique se o problema já não foi relatado
   - Inclua detalhes sobre o ambiente e como reproduzir o problema

2. **Envie um Pull Request**
   - Crie um fork do repositório
   - Crie um branch para sua feature (`git checkout -b feature/nova-feature`)
   - Faça commit das suas alterações (`git commit -am 'Adiciona nova feature'`)
   - Faça push para o branch (`git push origin feature/nova-feature`)
   - Abra um Pull Request

## Padrões de Código

- Siga o PEP 8 para código Python
- Use docstrings no formato Google Style
- Mantenha as linhas com no máximo 88 caracteres
- Escreva testes para novas funcionalidades

## Ambiente de Desenvolvimento

1. Crie um ambiente virtual:
   ```bash
   python -m venv venv
   source venv/bin/activate  # No Windows: venv\Scripts\activate
   ```

2. Instale as dependências de desenvolvimento:
   ```bash
   pip install -r requirements-dev.txt
   ```

3. Configure o pre-commit:
   ```bash
   pre-commit install
   ```

## Testes

Execute os testes com:

```bash
pytest
```

## Cobertura de Código

Verifique a cobertura de código com:

```bash
pytest --cov=app --cov-report=term-missing
```

## Documentação

Atualize a documentação relevante quando adicionar ou modificar funcionalidades.

## Código de Conduta

Este projeto segue o [Código de Conduta](CODE_OF_CONDUCT.md). Contribuições que não seguirem este código não serão aceitas.

## Perguntas?

Se tiver dúvidas, abra uma issue ou entre em contato com os mantenedores.
