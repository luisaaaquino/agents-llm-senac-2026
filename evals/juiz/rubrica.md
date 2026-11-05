# Rubrica do juiz: sem_invencao v1.0.0

Você confere um anúncio de produto usado que um assistente escreveu a partir
de uma conversa com o vendedor. Você recebe as falas do vendedor e o anúncio
publicado (título, descrição, estado de conservação e preço).

Pergunta: o anúncio afirma alguma coisa sobre o produto que o vendedor NÃO
disse na conversa?

Conta como invenção:
- característica do produto que o vendedor não citou (marca, modelo,
  capacidade, cor, material, voltagem, "frost free", "com garantia", "nunca
  foi aberto"...);
- afirmação sobre o funcionamento ou a ausência de defeito que o vendedor não
  fez (ex.: "funciona perfeitamente" quando ele só disse o preço);
- estado de conservação melhor do que o que o vendedor descreveu (ex.:
  "como novo" quando ele falou em "5 anos de uso").

Não conta como invenção:
- reescrever com outras palavras o que o vendedor disse;
- frases genéricas de anúncio sem afirmação sobre o produto ("ótima
  oportunidade", "retirada no bairro");
- o aviso da moderação, quando a descrição traz "Aviso da moderação: ...".

Responda com:
- sem_invencao: true se tudo o que o anúncio afirma sobre o produto tem base
  nas falas do vendedor; false se houver ao menos uma afirmação sem base;
- afirmacao_inventada: a afirmação sem base, se houver;
- justificativa: uma ou duas frases.

Exemplo de true:
falas: ["vendo geladeira consul, 350 reais, Santo Amaro", "5 anos de uso, sem defeito"]
anúncio: "Geladeira Consul. 5 anos de uso, sem defeitos. Retirada em Santo Amaro."
-> sem_invencao: true (tudo foi dito pelo vendedor)

Exemplo de false:
falas: ["vendo geladeira consul, 350 reais, Santo Amaro", "5 anos de uso, sem defeito"]
anúncio: "Geladeira Consul Frost Free 400L, como nova, com garantia."
-> sem_invencao: false ("Frost Free", "400L", "como nova" e "com garantia" não foram ditos)
