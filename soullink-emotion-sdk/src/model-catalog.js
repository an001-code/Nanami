export const modelCatalog = [
  {
    id: "lss",
    modelDir: "LSS",
    modelFile: "LSS.model3.json",
    displayName: "LSS",
    view: { scale: 1, x: 0, y: 0 }
  }
];

export function findModel(modelId) {
  return modelCatalog.find((model) => model.id === modelId) ?? modelCatalog[0];
}

export function modelAssetUrl(model, fileName) {
  return `/l2d/${model.modelDir}/${fileName}`;
}
