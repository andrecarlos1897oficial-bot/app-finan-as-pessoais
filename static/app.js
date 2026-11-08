/* Minhas Finanças — JS puro, sem framework.
   Só melhorias de experiência: o app funciona sem este arquivo. */
(function () {
  "use strict";

  // 1. Some com os avisos de sucesso depois de alguns segundos.
  var avisos = document.querySelectorAll(".aviso-sucesso");
  if (avisos.length) {
    window.setTimeout(function () {
      for (var i = 0; i < avisos.length; i += 1) {
        avisos[i].classList.add("aviso-saindo");
      }
    }, 6000);
  }

  // 2. Anima o gráfico de rosca na primeira pintura.
  var rosca = document.querySelector(".rosca");
  if (rosca) {
    window.requestAnimationFrame(function () {
      rosca.classList.add("rosca-pronta");
    });
  }

  var adicionarSheet = document.querySelector("[data-add-sheet]");
  if (adicionarSheet) {
    var fecharSheet = adicionarSheet.querySelector(".adicionar-fechar");
    var focaveis = adicionarSheet.querySelectorAll("a[href], button:not([disabled])");

    if (fecharSheet) {
      fecharSheet.focus();
    }

    document.addEventListener("keydown", function (event) {
      if (event.key === "Escape" && fecharSheet) {
        event.preventDefault();
        fecharSheet.click();
        return;
      }

      if (event.key !== "Tab" || focaveis.length === 0) {
        return;
      }

      var primeiro = focaveis[0];
      var ultimo = focaveis[focaveis.length - 1];
      if (event.shiftKey && document.activeElement === primeiro) {
        event.preventDefault();
        ultimo.focus();
      } else if (!event.shiftKey && document.activeElement === ultimo) {
        event.preventDefault();
        primeiro.focus();
      }
    });
  }

  var buscasCategoria = document.querySelectorAll("[data-category-search]");
  for (var buscaIndex = 0; buscaIndex < buscasCategoria.length; buscaIndex += 1) {
    buscasCategoria[buscaIndex].addEventListener("input", function () {
      var termo = this.value.trim().toLocaleLowerCase("pt-BR")
        .normalize("NFD").replace(/[\u0300-\u036f]/g, "");
      var grupoCategoria = this.closest(".grupo");
      var opcoes = grupoCategoria.querySelectorAll(".opcao");
      var totalVisivel = 0;
      for (var opcaoIndex = 0; opcaoIndex < opcoes.length; opcaoIndex += 1) {
        var nome = opcoes[opcaoIndex].textContent.toLocaleLowerCase("pt-BR")
          .normalize("NFD").replace(/[\u0300-\u036f]/g, "");
        opcoes[opcaoIndex].hidden = nome.indexOf(termo) === -1;
        if (!opcoes[opcaoIndex].hidden) {
          totalVisivel += 1;
        }
      }
      var semResultados = grupoCategoria.querySelector("[data-category-empty]");
      if (semResultados) {
        semResultados.hidden = totalVisivel > 0;
      }
    });
  }

  // 3. Formata o campo de valor ao sair do campo (1.234,56).
  function formatarValor(texto) {
    var limpo = texto.replace(/R\$/g, "").replace(/\s/g, "");
    if (!limpo) {
      return "";
    }

    var normalizado = limpo;
    if (/^\d{1,3}(\.\d{3})+(,\d{1,2})?$/.test(limpo)) {
      normalizado = limpo.replace(/\./g, "").replace(",", ".");
    } else if (/^\d{1,9}(,\d{1,2})?$/.test(limpo)) {
      normalizado = limpo.replace(",", ".");
    } else if (!/^\d{1,9}(\.\d{1,2})?$/.test(limpo)) {
      return texto; // deixa o servidor mostrar o erro; não mascara entrada inválida
    }

    var numero = Number(normalizado);
    if (!isFinite(numero) || numero <= 0) {
      return texto;
    }

    return numero.toLocaleString("pt-BR", {
      minimumFractionDigits: 2,
      maximumFractionDigits: 2
    });
  }

  var camposValor = document.querySelectorAll('input[name="valor"], input[name="valor_total"]');
  for (var i = 0; i < camposValor.length; i += 1) {
    camposValor[i].addEventListener("blur", function () {
      this.value = formatarValor(this.value);
    });
  }

  // 4. Erro de validação: leva o foco ao primeiro campo do formulário.
  var erro = document.querySelector(".aviso-erro");
  if (erro) {
    var formularioComErro = document.querySelector(".formulario");
    if (formularioComErro) {
      var primeiro = formularioComErro.querySelector("input:not([type=hidden]), select");
      if (primeiro) {
        primeiro.focus();
      }
    }
  }

  // 5. Evita envio duplicado do formulário.
  var formularios = document.querySelectorAll("form");
  for (var j = 0; j < formularios.length; j += 1) {
    var botaoEnvio = formularios[j].querySelector('button[type="submit"]');
    if (botaoEnvio) {
      botaoEnvio.setAttribute("data-texto-original", botaoEnvio.textContent);
    }

    formularios[j].addEventListener("invalid", function () {
      var botao = this.querySelector('button[type="submit"]');
      if (botao) {
        botao.disabled = false;
        botao.removeAttribute("aria-busy");
        botao.textContent = botao.getAttribute("data-texto-original");
      }
    }, true);

    formularios[j].addEventListener("submit", function () {
      var botao = this.querySelector('button[type="submit"]');
      if (botao) {
        botao.disabled = true;
        botao.setAttribute("aria-busy", "true");
        botao.textContent = "Salvando...";
      }
    });
  }
})();
