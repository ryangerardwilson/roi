if command -v systemctl >/dev/null 2>&1; then
  if "${INSTALL_DIR}/${APP}" svc i; then
    "${INSTALL_DIR}/${APP}" svc on || true
  fi
fi
